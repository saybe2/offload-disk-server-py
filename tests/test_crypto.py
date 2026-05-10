"""
Тесты сервиса шифрования.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from services.crypto import CryptoService


class TestCryptoService:
    """Тесты для CryptoService."""
    
    def test_init_with_string_key(self):
        """Сервис должен инициализироваться со строковым ключом."""
        crypto = CryptoService('my-secret-key')
        assert crypto.key is not None
        assert len(crypto.key) == 32  # 256 бит
    
    def test_init_with_bytes_key(self):
        """Сервис должен принимать байтовый ключ."""
        crypto = CryptoService(b'my-secret-key')
        assert len(crypto.key) == 32
    
    def test_encrypt_decrypt_string(self):
        """Зашифрованный и расшифрованный текст должен совпадать."""
        crypto = CryptoService('test-key')
        original = 'Hello, World! Привет, мир! 🌍'
        original_bytes = original.encode('utf-8')
        
        result = crypto.encrypt(original_bytes)
        decrypted = crypto.decrypt(
            result['encrypted'],
            result['iv'],
            result['auth_tag']
        )
        
        assert decrypted == original_bytes
        assert decrypted.decode('utf-8') == original
    
    def test_encrypt_produces_unique_iv(self):
        """Каждое шифрование должно использовать новый IV."""
        crypto = CryptoService('test-key')
        data = b'Same data'
        
        result1 = crypto.encrypt(data)
        result2 = crypto.encrypt(data)
        
        # IV должны быть разными
        assert result1['iv'] != result2['iv']
        # Зашифрованные данные тоже должны отличаться
        assert result1['encrypted'] != result2['encrypted']
    
    def test_decrypt_with_wrong_key_fails(self):
        """Расшифровка чужим ключом должна падать."""
        crypto1 = CryptoService('key1')
        crypto2 = CryptoService('key2')
        
        result = crypto1.encrypt(b'Secret data')
        
        with pytest.raises(ValueError):
            crypto2.decrypt(
                result['encrypted'],
                result['iv'],
                result['auth_tag']
            )
    
    def test_decrypt_with_tampered_data_fails(self):
        """Изменённые данные должны вызывать ошибку (GCM auth)."""
        crypto = CryptoService('test-key')
        result = crypto.encrypt(b'Original data')
        
        # Меняем зашифрованные данные
        tampered = bytearray(result['encrypted'])
        tampered[0] ^= 0xFF  # Инвертируем первый байт
        
        with pytest.raises(ValueError):
            crypto.decrypt(
                bytes(tampered),
                result['iv'],
                result['auth_tag']
            )
    
    def test_encrypt_empty_data(self):
        """Шифрование пустых данных должно работать."""
        crypto = CryptoService('test-key')
        result = crypto.encrypt(b'')
        decrypted = crypto.decrypt(
            result['encrypted'],
            result['iv'],
            result['auth_tag']
        )
        assert decrypted == b''
    
    def test_encrypt_large_data(self):
        """Шифрование больших данных (10 МБ)."""
        crypto = CryptoService('test-key')
        data = os.urandom(10 * 1024 * 1024)  # 10 МБ
        
        result = crypto.encrypt(data)
        decrypted = crypto.decrypt(
            result['encrypted'],
            result['iv'],
            result['auth_tag']
        )
        
        assert len(decrypted) == len(data)
        assert decrypted == data
    
    def test_calculate_hash(self):
        """Хэш должен быть детерминированным."""
        hash1 = CryptoService.calculate_hash(b'test data')
        hash2 = CryptoService.calculate_hash(b'test data')
        hash3 = CryptoService.calculate_hash(b'different data')
        
        assert hash1 == hash2
        assert hash1 != hash3
        assert len(hash1) == 64  # SHA-256 hex = 64 символа
    
    def test_encrypt_chunk(self):
        """Шифрование чанка должно работать как обычное шифрование."""
        crypto = CryptoService('test-key')
        chunk = b'X' * 1024
        
        result = crypto.encrypt_chunk(chunk)
        assert 'encrypted' in result
        assert 'iv' in result
        assert 'auth_tag' in result
        
        decrypted = crypto.decrypt_chunk(
            result['encrypted'],
            result['iv'],
            result['auth_tag']
        )
        assert decrypted == chunk
    
    def test_same_key_produces_consistent_keys(self):
        """Одинаковый мастер-ключ должен давать одинаковый производный ключ."""
        crypto1 = CryptoService('same-key')
        crypto2 = CryptoService('same-key')
        
        assert crypto1.key == crypto2.key
        
        # Можно расшифровывать данные другого экземпляра
        result = crypto1.encrypt(b'test')
        decrypted = crypto2.decrypt(
            result['encrypted'],
            result['iv'],
            result['auth_tag']
        )
        assert decrypted == b'test'
