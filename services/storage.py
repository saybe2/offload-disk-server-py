"""
Сервис управления файловым хранилищем.
Объединяет шифрование и загрузку в Discord.
"""
import os
import mimetypes
from config import Config
from services.crypto import CryptoService
from services.discord import DiscordService


class StorageService:
    """
    Высокоуровневый сервис для работы с файлами.
    
    Координирует шифрование файлов и их загрузку в Discord,
    обеспечивая безопасное облачное хранение.
    
    Attributes:
        crypto: Сервис шифрования
        discord: Сервис Discord
    """
    
    def __init__(self, master_key=None, webhook_url=None):
        """
        Инициализирует сервис хранения.
        
        Args:
            master_key: Ключ шифрования (из конфига если не указан)
            webhook_url: Discord webhook URL (из конфига если не указан)
        """
        self.crypto = CryptoService(master_key or Config.MASTER_KEY)
        self.discord = DiscordService(webhook_url or Config.DISCORD_WEBHOOK_URL)
        self.chunk_size = Config.CHUNK_SIZE_BYTES
    
    def upload_file(self, file_path, user_id=None):
        """
        Загружает файл: шифрует и отправляет в Discord.
        
        Большие файлы автоматически разбиваются на чанки.
        
        Args:
            file_path: Путь к файлу
            user_id: ID пользователя (для метаданных)
            
        Returns:
            dict: {
                'original_name': str,
                'size': int,
                'encrypted_size': int,
                'mime_type': str,
                'parts': list[dict],  # Информация о частях
                'iv': str,            # Для однофайловой загрузки
                'auth_tag': str       # Для однофайловой загрузки
            }
        """
        file_size = os.path.getsize(file_path)
        filename = os.path.basename(file_path)
        mime_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        
        # Для небольших файлов - простая загрузка
        if file_size <= self.chunk_size:
            return self._upload_single(file_path, filename, mime_type, user_id)
        
        # Для больших файлов - разбиваем на чанки
        return self._upload_chunked(file_path, filename, mime_type, user_id)
    
    def _upload_single(self, file_path, filename, mime_type, user_id):
        """Загружает файл одним куском."""
        with open(file_path, 'rb') as f:
            data = f.read()
        
        # Шифруем
        encrypted = self.crypto.encrypt(data)
        
        # Загружаем в Discord
        content = f'file:{filename} user:{user_id}'
        result = self.discord.upload_bytes(
            encrypted['encrypted'],
            f'{filename}.enc',
            content
        )
        
        # Формируем информацию о части
        part = {
            'index': 0,
            'url': result['url'],
            'message_id': result['message_id'],
            'size': result['size'],
            'hash': self.crypto.calculate_hash(encrypted['encrypted']),
            'iv': encrypted['iv'],
            'auth_tag': encrypted['auth_tag']
        }
        
        return {
            'original_name': filename,
            'size': len(data),
            'encrypted_size': result['size'],
            'mime_type': mime_type,
            'parts': [part],
            'iv': encrypted['iv'],
            'auth_tag': encrypted['auth_tag']
        }
    
    def _upload_chunked(self, file_path, filename, mime_type, user_id):
        """Загружает большой файл по частям."""
        parts = []
        total_size = 0
        encrypted_size = 0
        
        with open(file_path, 'rb') as f:
            chunk_index = 0
            
            while True:
                chunk = f.read(self.chunk_size)
                if not chunk:
                    break
                
                total_size += len(chunk)
                
                # Шифруем чанк
                encrypted = self.crypto.encrypt_chunk(chunk)
                encrypted_size += len(encrypted['encrypted'])
                
                # Загружаем в Discord
                content = f'file:{filename} part:{chunk_index} user:{user_id}'
                result = self.discord.upload_bytes(
                    encrypted['encrypted'],
                    f'{filename}.part{chunk_index}.enc',
                    content
                )
                
                # Сохраняем информацию о части
                part = {
                    'index': chunk_index,
                    'url': result['url'],
                    'message_id': result['message_id'],
                    'size': result['size'],
                    'plain_size': len(chunk),
                    'hash': self.crypto.calculate_hash(encrypted['encrypted']),
                    'iv': encrypted['iv'],
                    'auth_tag': encrypted['auth_tag']
                }
                parts.append(part)
                chunk_index += 1
        
        return {
            'original_name': filename,
            'size': total_size,
            'encrypted_size': encrypted_size,
            'mime_type': mime_type,
            'parts': parts,
            'iv': '',      # У каждого чанка свой IV
            'auth_tag': '' # У каждого чанка свой auth_tag
        }
    
    def download_file(self, file_info, output_path):
        """
        Скачивает и расшифровывает файл.
        
        Args:
            file_info: dict с информацией о файле (parts, iv, auth_tag)
            output_path: Путь для сохранения
        """
        parts = file_info.get('parts', [])
        
        if not parts:
            raise ValueError('Нет информации о частях файла')
        
        # Сортируем части по индексу
        parts = sorted(parts, key=lambda p: p['index'])
        
        # Однофайловая загрузка
        if len(parts) == 1:
            self._download_single(parts[0], file_info, output_path)
        else:
            # Многофайловая загрузка
            self._download_chunked(parts, output_path)
    
    def _download_single(self, part, file_info, output_path):
        """Скачивает и расшифровывает один файл."""
        # Скачиваем зашифрованные данные
        encrypted_data = self.discord.download_bytes(part['url'])
        
        # Получаем IV и auth_tag (из part или из file_info)
        iv = part.get('iv') or file_info.get('iv')
        auth_tag = part.get('auth_tag') or file_info.get('auth_tag')
        
        if not iv or not auth_tag:
            raise ValueError('Отсутствуют данные для расшифровки (iv/auth_tag)')
        
        # Расшифровываем
        decrypted = self.crypto.decrypt(encrypted_data, iv, auth_tag)
        
        # Сохраняем
        with open(output_path, 'wb') as f:
            f.write(decrypted)
    
    def _download_chunked(self, parts, output_path):
        """Скачивает и расшифровывает файл по частям."""
        with open(output_path, 'wb') as f:
            for part in parts:
                # Скачиваем чанк
                encrypted_data = self.discord.download_bytes(part['url'])
                
                # Расшифровываем
                iv = part['iv']
                auth_tag = part['auth_tag']
                decrypted = self.crypto.decrypt_chunk(encrypted_data, iv, auth_tag)
                
                # Записываем
                f.write(decrypted)
    
    def delete_file(self, file_info):
        """
        Удаляет файл из Discord.
        
        Args:
            file_info: dict с информацией о файле
            
        Returns:
            int: Количество успешно удалённых частей
        """
        parts = file_info.get('parts', [])
        deleted_count = 0
        
        for part in parts:
            message_id = part.get('message_id')
            if message_id and self.discord.delete_message(message_id):
                deleted_count += 1
        
        return deleted_count
    
    def refresh_urls(self, file_info):
        """
        Обновляет URL файлов (Discord периодически меняет ссылки).
        
        Args:
            file_info: dict с информацией о файле
            
        Returns:
            list: Обновлённый список частей
        """
        parts = file_info.get('parts', [])
        updated_parts = []
        
        for part in parts:
            message_id = part.get('message_id')
            if message_id:
                new_url = self.discord.refresh_url(message_id)
                if new_url:
                    part['url'] = new_url
            updated_parts.append(part)
        
        return updated_parts
