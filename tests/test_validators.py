"""
Тесты валидаторов.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from services.validators import (
    ValidationError,
    validate_username,
    validate_password,
    validate_folder_name,
    validate_file_name,
    validate_positive_int
)


class TestValidateUsername:
    """Тесты validate_username."""
    
    def test_valid_username(self):
        assert validate_username('user123') == 'user123'
        assert validate_username('admin_user') == 'admin_user'
        assert validate_username('test-user') == 'test-user'
    
    def test_empty_username(self):
        with pytest.raises(ValidationError):
            validate_username('')
        with pytest.raises(ValidationError):
            validate_username(None)
    
    def test_too_short(self):
        with pytest.raises(ValidationError):
            validate_username('ab')
    
    def test_too_long(self):
        with pytest.raises(ValidationError):
            validate_username('a' * 81)
    
    def test_invalid_chars(self):
        with pytest.raises(ValidationError):
            validate_username('user@example.com')
        with pytest.raises(ValidationError):
            validate_username('user space')
        with pytest.raises(ValidationError):
            validate_username('user!')
    
    def test_strip_whitespace(self):
        assert validate_username('  user123  ') == 'user123'


class TestValidatePassword:
    """Тесты validate_password."""
    
    def test_valid_password(self):
        assert validate_password('password123') == 'password123'
    
    def test_empty_password(self):
        with pytest.raises(ValidationError):
            validate_password('')
    
    def test_too_short(self):
        with pytest.raises(ValidationError):
            validate_password('12345')
    
    def test_too_long(self):
        with pytest.raises(ValidationError):
            validate_password('a' * 129)
    
    def test_minimum_length(self):
        assert validate_password('123456') == '123456'


class TestValidateFolderName:
    """Тесты validate_folder_name."""
    
    def test_valid_name(self):
        assert validate_folder_name('My Documents') == 'My Documents'
        assert validate_folder_name('Папка') == 'Папка'
    
    def test_empty_name(self):
        with pytest.raises(ValidationError):
            validate_folder_name('')
    
    def test_forbidden_chars(self):
        for char in '<>:"/\\|?*':
            with pytest.raises(ValidationError):
                validate_folder_name(f'name{char}')
    
    def test_too_long(self):
        with pytest.raises(ValidationError):
            validate_folder_name('a' * 256)
    
    def test_only_dots(self):
        with pytest.raises(ValidationError):
            validate_folder_name('...')


class TestValidateFileName:
    """Тесты validate_file_name."""
    
    def test_valid_name(self):
        assert validate_file_name('photo.jpg') == 'photo.jpg'
        assert validate_file_name('document.pdf') == 'document.pdf'
    
    def test_empty(self):
        with pytest.raises(ValidationError):
            validate_file_name('')
    
    def test_forbidden_chars(self):
        with pytest.raises(ValidationError):
            validate_file_name('file<>.txt')
    
    def test_strip(self):
        assert validate_file_name('  file.txt  ') == 'file.txt'


class TestValidatePositiveInt:
    """Тесты validate_positive_int."""
    
    def test_valid_int(self):
        assert validate_positive_int(1) == 1
        assert validate_positive_int(100) == 100
        assert validate_positive_int('42') == 42
    
    def test_zero(self):
        with pytest.raises(ValidationError):
            validate_positive_int(0)
    
    def test_negative(self):
        with pytest.raises(ValidationError):
            validate_positive_int(-5)
    
    def test_string(self):
        with pytest.raises(ValidationError):
            validate_positive_int('not a number')
    
    def test_none(self):
        with pytest.raises(ValidationError):
            validate_positive_int(None)
