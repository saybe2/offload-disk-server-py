"""
Инициализация пакета services.
"""
from services.crypto import CryptoService
from services.discord import DiscordService
from services.storage import StorageService

__all__ = ['CryptoService', 'DiscordService', 'StorageService']
