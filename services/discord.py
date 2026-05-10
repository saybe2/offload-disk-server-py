"""
Сервис для работы с Discord Webhook.
Загружает и скачивает файлы через Discord CDN.
"""
import os
import time
import requests
from config import Config


class DiscordService:
    """
    Сервис для загрузки и скачивания файлов через Discord Webhook.
    
    Discord позволяет загружать файлы до ~25МБ через webhook,
    которые затем хранятся на CDN Discord бессрочно.
    
    Attributes:
        webhook_url: URL Discord webhook для загрузки файлов
        max_retries: Максимальное количество попыток при ошибке
        retry_delay: Базовая задержка между попытками (секунды)
    """
    
    # Максимальный размер файла для Discord (в байтах)
    MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB
    
    def __init__(self, webhook_url=None):
        """
        Инициализирует сервис.
        
        Args:
            webhook_url: URL webhook (если не указан, берётся из конфига)
        """
        self.webhook_url = webhook_url or Config.DISCORD_WEBHOOK_URL
        self.max_retries = 5
        self.retry_delay = 1.5  # секунды
        
        if not self.webhook_url:
            raise ValueError('Discord webhook URL не настроен')
    
    def _request_with_retry(self, method, url, **kwargs):
        """
        Выполняет HTTP запрос с повторными попытками при ошибках.
        
        Args:
            method: HTTP метод ('get', 'post', 'delete')
            url: URL для запроса
            **kwargs: Дополнительные параметры для requests
            
        Returns:
            requests.Response: Ответ сервера
            
        Raises:
            Exception: При исчерпании попыток
        """
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                response = getattr(requests, method)(url, **kwargs, timeout=60)
                
                # Обработка rate limiting
                if response.status_code == 429:
                    retry_after = response.json().get('retry_after', 5)
                    time.sleep(retry_after)
                    continue
                
                # Успешный ответ
                if response.ok:
                    return response
                
                # Серверные ошибки - повторяем
                if 500 <= response.status_code < 600:
                    last_error = f'Серверная ошибка: {response.status_code}'
                    time.sleep(self.retry_delay * (2 ** attempt))
                    continue
                
                # Клиентские ошибки - не повторяем
                response.raise_for_status()
                
            except requests.exceptions.RequestException as e:
                last_error = str(e)
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))
                    continue
        
        raise Exception(f'Ошибка после {self.max_retries} попыток: {last_error}')
    
    def upload_bytes(self, data, filename, content=''):
        """
        Загружает байты в Discord как файл.
        
        Args:
            data: Байты для загрузки
            filename: Имя файла в Discord
            content: Текстовое сообщение к файлу
            
        Returns:
            dict: {
                'url': str,        # URL файла на CDN
                'message_id': str, # ID сообщения в Discord
                'size': int        # Размер загруженного файла
            }
            
        Raises:
            ValueError: Если файл слишком большой
            Exception: При ошибке загрузки
        """
        if len(data) > self.MAX_FILE_SIZE:
            raise ValueError(f'Файл слишком большой: {len(data)} байт '
                           f'(максимум {self.MAX_FILE_SIZE})')
        
        files = {
            'file': (filename, data)
        }
        payload = {
            'content': content[:2000] if content else ''  # Discord лимит
        }
        
        response = self._request_with_retry(
            'post',
            f'{self.webhook_url}?wait=true',
            files=files,
            data=payload
        )
        
        result = response.json()
        
        # Извлекаем информацию о загруженном файле
        attachments = result.get('attachments', [])
        if not attachments:
            raise Exception('Discord не вернул информацию о файле')
        
        attachment = attachments[0]
        
        return {
            'url': attachment['url'],
            'message_id': str(result['id']),
            'size': attachment.get('size', len(data))
        }
    
    def upload_file(self, file_path, content=''):
        """
        Загружает файл в Discord.
        
        Args:
            file_path: Путь к файлу
            content: Текстовое сообщение
            
        Returns:
            dict: {'url': str, 'message_id': str, 'size': int}
        """
        filename = os.path.basename(file_path)
        
        with open(file_path, 'rb') as f:
            data = f.read()
        
        return self.upload_bytes(data, filename, content)
    
    def download_bytes(self, url):
        """
        Скачивает файл по URL.
        
        Args:
            url: URL файла (обычно Discord CDN)
            
        Returns:
            bytes: Содержимое файла
        """
        response = self._request_with_retry('get', url)
        return response.content
    
    def download_file(self, url, output_path):
        """
        Скачивает файл и сохраняет на диск.
        
        Args:
            url: URL файла
            output_path: Путь для сохранения
        """
        data = self.download_bytes(url)
        
        with open(output_path, 'wb') as f:
            f.write(data)
    
    def delete_message(self, message_id):
        """
        Удаляет сообщение (и прикреплённый файл) из Discord.
        
        Args:
            message_id: ID сообщения для удаления
            
        Returns:
            bool: True если удалено успешно
        """
        try:
            self._request_with_retry(
                'delete',
                f'{self.webhook_url}/messages/{message_id}'
            )
            return True
        except Exception:
            return False
    
    def refresh_url(self, message_id):
        """
        Получает актуальный URL файла (Discord периодически обновляет ссылки).
        
        Args:
            message_id: ID сообщения с файлом
            
        Returns:
            str: Актуальный URL файла или None
        """
        try:
            response = self._request_with_retry(
                'get',
                f'{self.webhook_url}/messages/{message_id}'
            )
            result = response.json()
            attachments = result.get('attachments', [])
            if attachments:
                return attachments[0]['url']
        except Exception:
            pass
        return None
    
    def is_configured(self):
        """Проверяет, настроен ли webhook."""
        return bool(self.webhook_url)
