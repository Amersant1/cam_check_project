#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Удобный скрипт запуска проекта распознавания голоса
"""

import os
import sys
import subprocess
import platform
import argparse

def check_docker():
    """Проверка наличия Docker"""
    try:
        result = subprocess.run(['docker', '--version'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Docker найден: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass
    
    print("❌ Docker не найден. Установите Docker для использования контейнеров.")
    return False

def check_docker_compose():
    """Проверка наличия Docker Compose"""
    try:
        # Проверяем docker compose (новый способ)
        result = subprocess.run(['docker', 'compose', 'version'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Docker Compose найден: {result.stdout.strip()}")
            return 'docker compose'
    except FileNotFoundError:
        pass
    
    try:
        # Проверяем docker-compose (старый способ)
        result = subprocess.run(['docker-compose', '--version'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Docker Compose найден: {result.stdout.strip()}")
            return 'docker-compose'
    except FileNotFoundError:
        pass
    
    print("❌ Docker Compose не найден.")
    return None

def run_docker_build():
    """Сборка Docker образа"""
    compose_cmd = check_docker_compose()
    if not compose_cmd:
        return False
    
    print("🔨 Сборка Docker образа...")
    cmd = compose_cmd.split() + ['build']
    result = subprocess.run(cmd)
    return result.returncode == 0

def run_docker_app():
    """Запуск приложения в Docker"""
    compose_cmd = check_docker_compose()
    if not compose_cmd:
        return False
    
    print("🚀 Запуск приложения в Docker...")
    cmd = compose_cmd.split() + ['run', '--rm', 'voice-recognition', 'python', 'app.py']
    subprocess.run(cmd)

def run_docker_examples():
    """Запуск примеров в Docker"""
    compose_cmd = check_docker_compose()
    if not compose_cmd:
        return False
    
    print("📚 Запуск примеров в Docker...")
    cmd = compose_cmd.split() + ['run', '--rm', 'voice-recognition', 'python', 'examples.py']
    subprocess.run(cmd)

def run_local_setup():
    """Локальная установка зависимостей"""
    print("📦 Установка зависимостей...")
    
    # Проверяем наличие pip
    try:
        subprocess.run([sys.executable, '-m', 'pip', '--version'], 
                      capture_output=True, check=True)
    except subprocess.CalledProcessError:
        print("❌ pip не найден. Установите Python с pip.")
        return False
    
    # Устанавливаем зависимости
    requirements_path = os.path.join('app', 'requirements.txt')
    if not os.path.exists(requirements_path):
        print(f"❌ Файл {requirements_path} не найден.")
        return False
    
    try:
        result = subprocess.run([
            sys.executable, '-m', 'pip', 'install', '-r', requirements_path
        ], check=True)
        print("✅ Зависимости установлены успешно")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка установки зависимостей: {e}")
        return False

def run_local_app():
    """Локальный запуск приложения"""
    app_path = os.path.join('app', 'app.py')
    if not os.path.exists(app_path):
        print(f"❌ Файл {app_path} не найден.")
        return
    
    print("🚀 Запуск приложения локально...")
    os.chdir('app')
    subprocess.run([sys.executable, 'app.py'])

def run_local_examples():
    """Локальный запуск примеров"""
    examples_path = os.path.join('app', 'examples.py')
    if not os.path.exists(examples_path):
        print(f"❌ Файл {examples_path} не найден.")
        return
    
    print("📚 Запуск примеров локально...")
    os.chdir('app')
    subprocess.run([sys.executable, 'examples.py'])

def show_system_info():
    """Показать информацию о системе"""
    print("🖥️ Информация о системе:")
    print(f"  ОС: {platform.system()} {platform.release()}")
    print(f"  Python: {sys.version}")
    print(f"  Архитектура: {platform.machine()}")
    
    # Проверяем аудио устройства (если возможно)
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        input_devices = [d for d in devices if d['max_input_channels'] > 0]
        print(f"  Аудио устройства ввода: {len(input_devices)}")
        for i, device in enumerate(input_devices[:3]):  # Показываем первые 3
            print(f"    {i}: {device['name']}")
    except ImportError:
        print("  Аудио устройства: требуется установка sounddevice")
    except Exception as e:
        print(f"  Аудио устройства: ошибка проверки ({e})")

def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(
        description='Скрипт запуска проекта распознавания голоса'
    )
    parser.add_argument('--info', action='store_true', 
                       help='Показать информацию о системе')
    parser.add_argument('--docker', action='store_true',
                       help='Использовать Docker')
    parser.add_argument('--local', action='store_true',
                       help='Запуск локально')
    parser.add_argument('--setup', action='store_true',
                       help='Установить зависимости')
    parser.add_argument('--examples', action='store_true',
                       help='Запустить примеры')
    parser.add_argument('--build', action='store_true',
                       help='Собрать Docker образ')
    
    args = parser.parse_args()
    
    print("🎤 Проект распознавания голоса")
    print("=" * 40)
    
    if args.info:
        show_system_info()
        return
    
    if args.build:
        if check_docker():
            run_docker_build()
        return
    
    if args.docker:
        if check_docker():
            if args.examples:
                run_docker_examples()
            else:
                run_docker_app()
        return
    
    if args.local:
        if args.setup:
            if run_local_setup():
                print("✅ Готово! Теперь можно запускать приложение.")
        elif args.examples:
            run_local_examples()
        else:
            run_local_app()
        return
    
    # Интерактивное меню
    while True:
        print("\n🎯 Выберите действие:")
        print("1. Запуск в Docker (приложение)")
        print("2. Запуск в Docker (примеры)")
        print("3. Локальная установка зависимостей")
        print("4. Локальный запуск приложения")
        print("5. Локальный запуск примеров")
        print("6. Сборка Docker образа")
        print("7. Информация о системе")
        print("0. Выход")
        
        try:
            choice = input("\nВведите номер (0-7): ").strip()
            
            if choice == '0':
                print("👋 До свидания!")
                break
            elif choice == '1':
                if check_docker():
                    run_docker_app()
            elif choice == '2':
                if check_docker():
                    run_docker_examples()
            elif choice == '3':
                run_local_setup()
            elif choice == '4':
                run_local_app()
            elif choice == '5':
                run_local_examples()
            elif choice == '6':
                if check_docker():
                    run_docker_build()
            elif choice == '7':
                show_system_info()
            else:
                print("❌ Неверный выбор, попробуйте снова")
                
        except KeyboardInterrupt:
            print("\n👋 Выход из программы")
            break
        except Exception as e:
            print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    main()
