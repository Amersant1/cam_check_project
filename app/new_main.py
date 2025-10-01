import os
import shutil
import uvicorn
import pathlib
from pathlib import Path
from fastapi import FastAPI, File, UploadFile
from faster_whisper import WhisperModel
from pyannote.audio import Pipeline
from datetime import datetime

os.environ['LD_LIBRARY_PATH'] = "/home/fiornrrn/code/cam_check_project/.venv/lib/python3.11/site-packages/nvidia/cudnn/lib:" + os.environ.get('LD_LIBRARY_PATH', '')

pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", use_auth_token=os.environ['HF_TOKEN'])
model = WhisperModel("medium", device="cuda", compute_type="float16")

app = FastAPI()
Path("./audios").mkdir(exist_ok=True)

@app.post("/transcribe/")
async def transcribe(file: UploadFile = File(...)):
    filename = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    path = f"./audios/{filename}{pathlib.Path(file.filename).suffix if file.filename else ''}"
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    diarization = pipeline(path)
    segments = list(model.transcribe(path, language="ru")[0])

    text = ""
    for seg in segments:
        mid = (seg.start + seg.end) / 2
        speaker = next((lbl for t, _, lbl in diarization.itertracks(yield_label=True) if t.start <= mid <= t.end), "UNK")
        text += f"{speaker}: {seg.text}\n"

    transcription_path = f"./transcriptions/{filename}.log"
    with open(transcription_path, "w") as f:
        f.write(text)

    # Path(path).unlink()
    return {"text": text}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
