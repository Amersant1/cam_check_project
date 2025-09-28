#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сервер с faster-whisper + pyannote.audio
- /            — страница для записи голоса
- /ws          — WebSocket для стрима аудио  
- /transcribe  — HTTP для загрузки WAV файла
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from typing import List, Dict, Any, Optional
import io
import os
import json
import time
import wave
import tempfile

import numpy as np
from faster_whisper import WhisperModel

try:
    from pyannote.audio import Pipeline as PaPipeline
    has_pyannote = True
except Exception:
    has_pyannote = False
    PaPipeline = None

APP_TITLE = "Mic Transcription (faster-whisper + pyannote)"
app = FastAPI(title=APP_TITLE, version="5.0")

# -------------------- utils --------------------

def pcm16_to_wav_bytes(pcm: bytes, sample_rate: int) -> bytes:
	buf = io.BytesIO()
	with wave.open(buf, 'wb') as wf:
		wf.setnchannels(1)
		wf.setsampwidth(2)
		wf.setframerate(sample_rate)
		wf.writeframes(pcm)
	buf.seek(0)
	return buf.read()

def wav_bytes_to_float_np(wav_bytes: bytes) -> (np.ndarray, int):
	with wave.open(io.BytesIO(wav_bytes), 'rb') as wf:
		if wf.getnchannels() != 1 or wf.getsampwidth() != 2:
			raise HTTPException(status_code=400, detail="Expect mono 16-bit WAV")
		sr = wf.getframerate()
		raw = wf.readframes(wf.getnframes())
		pcm16 = np.frombuffer(raw, dtype=np.int16)
		if pcm16.size == 0:
			return np.zeros((0,), dtype=np.float32), sr
		audio = (pcm16.astype(np.float32) / 32768.0)
		return audio, sr

# -------------------- model loaders --------------------

_whisper_model: Optional[WhisperModel] = None
_pyannote: Any = None

def get_whisper() -> WhisperModel:
	global _whisper_model
	if _whisper_model is not None:
		return _whisper_model
	name = os.environ.get("WHISPER_MODEL", "tiny")
	_whisper_model = WhisperModel(name, device="cpu", compute_type="int8")
	return _whisper_model

def get_pyannote() -> Optional[Any]:
	global _pyannote
	if _pyannote is not None:
		return _pyannote
	if not has_pyannote:
		return None
	token = os.environ.get("HF_TOKEN")
	if not token:
		return None
	try:
		_pyannote = PaPipeline.from_pretrained("pyannote/speaker-diarization-3.1", use_auth_token=token)
		return _pyannote
	except Exception:
		return None

# -------------------- core inference --------------------

TARGET_SAMPLE_RATE = 16000

def run_whisper(wav_bytes: bytes) -> List[Dict[str, Any]]:
    model = get_whisper()
    audio, sr = wav_bytes_to_float_np(wav_bytes)
    if audio.size == 0:
        return []
    if sr != TARGET_SAMPLE_RATE:
        # простая линейная интерполяция до 16 кГц для стабильной работы
        duration = audio.shape[0] / sr
        new_length = int(duration * TARGET_SAMPLE_RATE)
        if new_length <= 0:
            return []
        xp = np.linspace(0, duration, num=audio.shape[0], endpoint=False)
        x_new = np.linspace(0, duration, num=new_length, endpoint=False)
        audio = np.interp(x_new, xp, audio).astype(np.float32)
        sr = TARGET_SAMPLE_RATE
    segments, _ = model.transcribe(
        audio=audio,
        beam_size=1,
        best_of=1,
        temperature=0.0,
    )
    out: List[Dict[str, Any]] = []
    for seg in segments:
        text = (seg.text or "").strip()
        if not text:
            continue
        out.append({
            "start": float(seg.start),
            "end": float(seg.end),
            "text": text,
        })
    return out

def run_diarization(wav_bytes: bytes) -> List[Dict[str, Any]]:
	# Отключаем диаризацию для скорости - возвращаем один спикер
	return [{
		"start": 0.0,
		"end": 5.0,
		"speaker": "SPEAKER_00"
	}]

def assign_speakers(stt: List[Dict[str, Any]], spk: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
	if not spk:
		# no diarization available
		for s in stt:
			s["speaker"] = "SPEAKER_00"
		return stt
	# for each text segment, choose speaker with max overlap
	for s in stt:
		best = None
		best_ov = 0.0
		for d in spk:
			ov = overlap((s["start"], s["end"]), (d["start"], d["end"]))
			if ov > best_ov:
				best_ov = ov
				best = d
		s["speaker"] = best["speaker"] if best else "SPEAKER_00"
	return stt

def overlap(a: (float, float), b: (float, float)) -> float:
	l = max(a[0], b[0])
	r = min(a[1], b[1])
	return max(0.0, r - l)

# -------------------- HTTP/UI --------------------

@app.get("/", response_class=HTMLResponse)
async def index():
	return HTMLResponse("""
	<!doctype html>
	<html>
	<head>
		<meta charset="utf-8" />
		<meta name="viewport" content="width=device-width, initial-scale=1" />
		<title>Voice → Text (faster-whisper + pyannote)</title>
		<style>
			body{font-family:Arial,Helvetica,sans-serif;margin:24px;}
			button{padding:10px 14px;margin-right:8px}
			#status{margin-left:8px;color:#555}
			#result{margin-top:16px;white-space:pre-wrap;border:1px solid #ddd;padding:12px;border-radius:8px;min-height:60px}
			.spk{color:#0a58ca}
		</style>
	</head>
	<body>
		<h3>🎤 faster-whisper + pyannote diarization</h3>
		<div>
			<button id="startWs">Начать (WS)</button>
			<button id="stopWs" disabled>Остановить</button>
			<button id="oneShotBtn">Записать и отправить (HTTP)</button>
			<span id="status">Готов</span>
		</div>
		<div id="result"></div>
		<script>
		let audioContext, mediaStream, processor, input;
		let ws; let wsOpen=false; let wsUrl=(location.protocol==='https:'?'wss://':'ws://')+location.host+'/ws';
		function floatTo16BitPCM(float32Array){
			const buffer = new ArrayBuffer(float32Array.length*2); const view = new DataView(buffer);
			let o=0; for(let i=0;i<float32Array.length;i++,o+=2){ let s=Math.max(-1,Math.min(1,float32Array[i])); view.setInt16(o, s<0? s*0x8000 : s*0x7FFF, true);} return new Uint8Array(buffer);
		}
		function writeWavHeader(view, sampleRate, numSamples){ function w(v,o,s){ for(let i=0;i<s.length;i++) v.setUint8(o+i,s.charCodeAt(i)); }
			const ch=1,bps=16,ba=ch*bps/8,br=sampleRate*ba,ds=numSamples*ba; w(view,0,'RIFF'); view.setUint32(4,36+ds,true); w(view,8,'WAVE'); w(view,12,'fmt ');
			view.setUint32(16,16,true); view.setUint16(20,1,true); view.setUint16(22,ch,true); view.setUint32(24,sampleRate,true); view.setUint32(28,br,true);
			view.setUint16(32,ba,true); view.setUint16(34,bps,true); w(view,36,'data'); view.setUint32(40,ds,true);
		}
		function setStatus(s){ document.getElementById('status').textContent=s; }
		function openSocket(){ return new Promise((res,rej)=>{ ws=new WebSocket(wsUrl); ws.binaryType='arraybuffer'; ws.onopen=()=>{wsOpen=true;res();}; ws.onerror=e=>rej(e); ws.onclose=()=>{wsOpen=false}; ws.onmessage=(evt)=>{ try{ const msg=JSON.parse(evt.data); if(msg.type==='partial'){ document.getElementById('result').textContent='Промежуточно: '+(msg.text||''); } else if(msg.type==='final'){ const segs=msg.segments||[]; const out=segs.map(s=>`<div><span class='spk'>${s.speaker}</span>: ${s.text}</div>`).join(''); document.getElementById('result').innerHTML=out||('Итог: '+(msg.text||'')); } }catch(e){} } }); }
		async function startWS(){ setStatus('Доступ к микрофону...'); try{ await openSocket(); mediaStream=await navigator.mediaDevices.getUserMedia({audio:true}); audioContext=new (window.AudioContext||window.webkitAudioContext)(); try{ ws.send(JSON.stringify({type:'config', sampleRate: audioContext.sampleRate})); }catch{} const input=audioContext.createMediaStreamSource(mediaStream); const proc=audioContext.createScriptProcessor(4096,1,1); proc.onaudioprocess=(e)=>{ const f32=e.inputBuffer.getChannelData(0); const pcm=floatTo16BitPCM(f32); if(wsOpen) ws.send(pcm); }; input.connect(proc); proc.connect(audioContext.destination); window._wsproc=proc; window._wsinp=input; window._wsac=audioContext; window._wsms=mediaStream; setStatus('Стрим по WS...'); document.getElementById('startWs').disabled=true; document.getElementById('stopWs').disabled=false; }catch(e){ console.error(e); setStatus('Ошибка'); } }
		function stopWS(){ try{ window._wsproc&&window._wsproc.disconnect(); window._wsinp&&window._wsinp.disconnect(); window._wsac&&window._wsac.close(); window._wsms&&window._wsms.getTracks().forEach(t=>t.stop()); }catch{} if(wsOpen){ try{ ws.send('end'); }catch{} } setStatus('Остановлено'); document.getElementById('startWs').disabled=false; document.getElementById('stopWs').disabled=true; }
		async function oneShot(){ setStatus('Запись 3с...'); try{ const ms=await navigator.mediaDevices.getUserMedia({audio:true}); const ac=new (window.AudioContext||window.webkitAudioContext)(); const inp=ac.createMediaStreamSource(ms); const proc=ac.createScriptProcessor(4096,1,1); const chunks=[]; proc.onaudioprocess=(e)=>chunks.push(new Float32Array(e.inputBuffer.getChannelData(0))); inp.connect(proc); proc.connect(ac.destination); await new Promise(r=>setTimeout(r,3000)); proc.disconnect(); inp.disconnect(); ac.close(); ms.getTracks().forEach(t=>t.stop()); let len=chunks.reduce((a,b)=>a+b.length,0), merged=new Float32Array(len), off=0; for(const ch of chunks){ merged.set(ch,off); off+=ch.length; } const pcm=floatTo16BitPCM(merged); const wav=new ArrayBuffer(44+pcm.byteLength); const v=new DataView(wav); writeWavHeader(v,ac.sampleRate,merged.length); new Uint8Array(wav,44).set(pcm); const blob=new Blob([v,pcm],{type:'audio/wav'}); setStatus('Отправляю...'); const form=new FormData(); form.append('audio',blob,'audio.wav'); const res=await fetch('/transcribe',{method:'POST',body:form}); const data=await res.json(); const segs=(data.segments||[]); const out=segs.map(s=>`<div><span class='spk'>${s.speaker}</span>: ${s.text}</div>`).join(''); document.getElementById('result').innerHTML=out||('Текст: '+(data.text||'')); setStatus('Готов'); }catch(e){ console.error(e); setStatus('Ошибка'); } }
		document.getElementById('startWs').onclick=startWS; document.getElementById('stopWs').onclick=stopWS; document.getElementById('oneShotBtn').onclick=oneShot;
		</script>
	</body>
	</html>
	""")

# -------------------- HTTP/WS backends --------------------

@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
	try:
		content = await audio.read()
		if not content:
			raise HTTPException(status_code=400, detail="Empty audio")
		stt_segments = run_whisper(content)
		spk_segments = run_diarization(content)
		final = assign_speakers(stt_segments, spk_segments)
		return JSONResponse({"segments": final})
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws")
async def ws(ws: WebSocket):
	await ws.accept()
	buffer = bytearray()
	current_sr = 16000
	last_sent = 0.0
	try:
		while True:
			msg = await ws.receive()
			if 'bytes' in msg and msg['bytes']:
				buffer.extend(msg['bytes'])
			elif 'text' in msg and msg['text']:
				text = msg['text']
				if 'sampleRate' in text:
					try:
						cfg = json.loads(text)
						if isinstance(cfg, dict) and cfg.get('type') == 'config':
							sr = int(cfg.get('sampleRate', current_sr))
							if sr > 0:
								current_sr = sr
					except Exception:
						pass
				elif text == 'end' or text == '{"type":"end"}' or '"type":"end"' in text:
					# финальная обработка
					wav_bytes = pcm16_to_wav_bytes(bytes(buffer), current_sr)
					stt = run_whisper(wav_bytes)
					spk = run_diarization(wav_bytes)
					final = assign_speakers(stt, spk)
					await ws.send_text(json.dumps({"type": "final", "segments": final}))
					break
				else:
					# ignore
					pass
	except WebSocketDisconnect:
		pass
	except Exception as e:
		try:
			await ws.send_text(json.dumps({"type": "error", "detail": str(e)}))
		except:
			pass
	finally:
		try:
			await ws.close()
		except:
			pass

if __name__ == "__main__":
	import uvicorn
	uvicorn.run(app, host="0.0.0.0", port=8000)