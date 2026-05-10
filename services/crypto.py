"""
Сервис шифрования файлов.
Реализует AES-256-GCM шифрование для безопасного хранения.
"""
import os
import base64
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class CryptoService:
    """
    Сервис для шифрования и расшифровки файлов.
    
    Использует AES-256-GCM для обеспечения конфиденциальности
    и целостности данных.
    
    Attributes:
        key: 256-битный ключ шифрования
    """
    
    # Размер IV (nonce) для GCM режима
    IV_SIZE = 12
    
    # Размер ключа в байтах (256 бит)
    KEY_SIZE = 32
    
    def __init__(self, master_key):
        """
        Инициализирует сервис с мастер-ключом.
        
        Args:
            master_key: Строка мастер-ключа (будет преобразована в 256 бит)
        """
        self.key = self._derive_key(master_key)
        self._cipher = AESGCM(self.key)
    
    def _derive_key(self, master_key):
        """
        Преобразует мастер-ключ в 256-битный ключ шифрования.
        
        Args:
            master_key: Исходная строка ключа
            
        Returns:
            bytes: 32-байтный ключ для AES-256
        """
        if isinstance(master_key, str):
            master_key = master_key.encode('utf-8')
        return hashlib.sha256(master_key).digest()
    
    def encrypt(self, data):
        """
        Шифрует данные с использованием AES-256-GCM.
        
        Args:
            data: Байты для шифрования
            
        Returns:
            dict: {'encrypted': bytes, 'iv': str, 'auth_tag': str}
                  iv и auth_tag закодированы в base64
        """
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        # Генерируем случайный IV
        iv = os.urandom(self.IV_SIZE)
        
        # Шифруем данные (GCM автоматически добавляет auth tag в конец)
        encrypted_with_tag = self._cipher.encrypt(iv, data, None)
        
        # В AESGCM auth_tag добавляется в конец зашифрованных данных
        # Размер auth_tag в AESGCM по умолчанию 16 байт
        encrypted_data = encrypted_with_tag[:-16]
        auth_tag = encrypted_with_tag[-16:]
        
        return {
            'encrypted': encrypted_data,
            'iv': base64.b64encode(iv).decode('utf-8'),
            'auth_tag': base64.b64encode(auth_tag).decode('utf-8')
        }
    
    def decrypt(self, encrypted_data, iv_b64, auth_tag_b64):
        """
        Расшифровывает данные.
        
        Args:
            encrypted_data: Зашифрованные байты
            iv_b64: IV в формате base64
            auth_tag_b64: Auth tag в формате base64
            
        Returns:
            bytes: Расшифрованные данные
            
        Raises:
            ValueError: При неверном ключе или повреждённых данных
        """
        try:
            iv = base64.b64decode(iv_b64)
            auth_tag = base64.b64decode(auth_tag_b64)
            
            # Собираем данные обратно (encrypted + auth_tag)
            encrypted_with_tag = encrypted_data + auth_tag
            
            # Расшифровываем
            return self._cipher.decrypt(iv, encrypted_with_tag, None)
        except Exception as e:
            raise ValueError(f'Ошибка расшифровки: {str(e)}')
    
    def encrypt_file(self, input_path, output_path):
        """
        Шифрует файл и сохраняет результат.
        
        Args:
            input_path: Путь к исходному файлу
            output_path: Путь для сохранения зашифрованного файла
            
        Returns:
            dict: {'iv': str, 'auth_tag': str, 'size': int}
        """
        with open(input_path, 'rb') as f:
            data = f.read()
        
        result = self.encrypt(data)
        
        with open(output_path, 'wb') as f:
            f.write(result['encrypted'])
        
        return {
            'iv': result['iv'],
            'auth_tag': result['auth_tag'],
            'size': len(result['encrypted'])
        }
    
    def decrypt_file(self, input_path, output_path, iv_b64, auth_tag_b64):
        """
        Расшифровывает файл и сохраняет результат.
        
        Args:
            input_path: Путь к зашифрованному файлу
            output_path: Путь для сохранения расшифрованного файла
            iv_b64: IV в формате base64
            auth_tag_b64: Auth tag в формате base64
        """
        with open(input_path, 'rb') as f:
            encrypted_data = f.read()
        
        decrypted = self.decrypt(encrypted_data, iv_b64, auth_tag_b64)
        
        with open(output_path, 'wb') as f:
            f.write(decrypted)
    
    def encrypt_chunk(self, chunk_data):
        """
        Шифрует чанк данных (для больших файлов).
        
        Каждый чанк получает свой уникальный IV.
        
        Args:
            chunk_data: Байты чанка
            
        Returns:
            dict: {'encrypted': bytes, 'iv': str, 'auth_tag': str}
        """
        return self.encrypt(chunk_data)
    
    def decrypt_chunk(self, encrypted_chunk, iv_b64, auth_tag_b64):
        """
        Расшифровывает чанк данных.
        
        Args:
            encrypted_chunk: Зашифрованные байты чанка
            iv_b64: IV чанка в base64
            auth_tag_b64: Auth tag чанка в base64
            
        Returns:
            bytes: Расшифрованные данные чанка
        """
        return self.decrypt(encrypted_chunk, iv_b64, auth_tag_b64)
    
    @staticmethod
    def calculate_hash(data):
        """
        Вычисляет SHA-256 хэш данных.
        
        Args:
            data: Байты для хэширования
            
        Returns:
            str: Хэш в шестнадцатеричном формате
        """
        if isinstance(data, str):
            data = data.encode('utf-8')
        return hashlib.sha256(data).hexdigest()
