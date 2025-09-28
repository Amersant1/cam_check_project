#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Система логирования для приложения
"""

import logging
import sys
from typing import Optional
from pathlib import Path
import time
from logging.handlers import RotatingFileHandler

class Logger:
    """Централизованная система логирования"""
    
    _instance: Optional['Logger'] = None
    _initialized = False
    
    def __new__(cls) -> 'Logger':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._setup_logging()
            self.__class__._initialized = True
    
    def _setup_logging(self):
        """Настройка системы логирования"""
        # Создаем папку для логов
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # Основной логгер
        self.logger = logging.getLogger("voice_recognition")
        self.logger.setLevel(logging.INFO)
        
        # Очищаем существующие обработчики
        self.logger.handlers.clear()
        
        # Форматтер
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Консольный обработчик
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # Файловый обработчик с ротацией
        file_handler = RotatingFileHandler(
            log_dir / "app.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        # Обработчик для ошибок
        error_handler = RotatingFileHandler(
            log_dir / "errors.log",
            maxBytes=5*1024*1024,  # 5MB
            backupCount=3
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        self.logger.addHandler(error_handler)
    
    def get_logger(self, name: Optional[str] = None) -> logging.Logger:
        """Получить логгер для модуля"""
        if name:
            return logging.getLogger(f"voice_recognition.{name}")
        return self.logger
    
    def info(self, message: str, module: Optional[str] = None):
        """Логирование информации"""
        logger = self.get_logger(module)
        logger.info(message)
    
    def debug(self, message: str, module: Optional[str] = None):
        """Логирование отладки"""
        logger = self.get_logger(module)
        logger.debug(message)
    
    def warning(self, message: str, module: Optional[str] = None):
        """Логирование предупреждений"""
        logger = self.get_logger(module)
        logger.warning(message)
    
    def error(self, message: str, module: Optional[str] = None, exc_info: bool = False):
        """Логирование ошибок"""
        logger = self.get_logger(module)
        logger.error(message, exc_info=exc_info)
    
    def critical(self, message: str, module: Optional[str] = None):
        """Логирование критических ошибок"""
        logger = self.get_logger(module)
        logger.critical(message)

# Глобальный экземпляр логгера
logger = Logger()

# Удобные функции для быстрого использования
def get_logger(module_name: str = None) -> logging.Logger:
    """Получить логгер для модуля"""
    return logger.get_logger(module_name)

def log_info(message: str, module: str = None):
    """Быстрое логирование информации"""
    logger.info(message, module)

def log_error(message: str, module: str = None, exc_info: bool = False):
    """Быстрое логирование ошибки"""
    logger.error(message, module, exc_info)

def log_warning(message: str, module: str = None):
    """Быстрое логирование предупреждения"""
    logger.warning(message, module)

def log_debug(message: str, module: str = None):
    """Быстрое логирование отладки"""
    logger.debug(message, module)
