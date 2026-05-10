"""
Тесты утилит для работы с файлами.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from services.file_utils import (
    get_file_extension,
    get_file_category,
    is_allowed_file,
    sanitize_filename,
    format_file_size,
    get_mime_type_icon,
    parse_content_range,
    generate_unique_filename
)


class TestGetFileExtension:
    """Тесты get_file_extension."""
    
    def test_normal_file(self):
        assert get_file_extension('photo.jpg') == 'jpg'
    
    def test_uppercase(self):
        assert get_file_extension('FILE.PNG') == 'png'
    
    def test_no_extension(self):
        assert get_file_extension('README') == ''
    
    def test_multiple_dots(self):
        assert get_file_extension('archive.tar.gz') == 'gz'
    
    def test_hidden_file(self):
        # Файл начинается с точки, но имеет расширение
        assert get_file_extension('.gitignore') == 'gitignore'


class TestGetFileCategory:
    """Тесты get_file_category."""
    
    def test_image(self):
        assert get_file_category('photo.jpg') == 'images'
        assert get_file_category('icon.png') == 'images'
    
    def test_video(self):
        assert get_file_category('movie.mp4') == 'videos'
    
    def test_audio(self):
        assert get_file_category('song.mp3') == 'audio'
    
    def test_document(self):
        assert get_file_category('report.pdf') == 'documents'
    
    def test_archive(self):
        assert get_file_category('files.zip') == 'archives'
    
    def test_code(self):
        assert get_file_category('script.py') == 'code'
        assert get_file_category('app.js') == 'code'
    
    def test_unknown(self):
        assert get_file_category('file.xyz') == 'other'


class TestIsAllowedFile:
    """Тесты is_allowed_file."""
    
    def test_allowed(self):
        assert is_allowed_file('photo.jpg') is True
        assert is_allowed_file('document.pdf') is True
    
    def test_no_extension_allowed(self):
        # Файлы без расширения разрешены
        assert is_allowed_file('Makefile') is True


class TestSanitizeFilename:
    """Тесты sanitize_filename."""
    
    def test_normal_filename(self):
        assert sanitize_filename('photo.jpg') == 'photo.jpg'
    
    def test_remove_path(self):
        assert sanitize_filename('/path/to/file.txt') == 'file.txt'
        assert sanitize_filename('C:\\path\\file.txt') == 'file.txt'
    
    def test_remove_dangerous_chars(self):
        result = sanitize_filename('file<>:|?.txt')
        for char in '<>:|?':
            assert char not in result
    
    def test_strip_dots_spaces(self):
        assert sanitize_filename('  .file.txt.  ') == 'file.txt'
    
    def test_long_filename(self):
        long_name = 'a' * 300 + '.txt'
        result = sanitize_filename(long_name)
        assert len(result) <= 200
    
    def test_empty_filename(self):
        result = sanitize_filename('')
        assert result.startswith('file_')


class TestFormatFileSize:
    """Тесты format_file_size."""
    
    def test_bytes(self):
        assert '500' in format_file_size(500)
        assert 'Б' in format_file_size(500)
    
    def test_kilobytes(self):
        result = format_file_size(2048)
        assert 'КБ' in result
    
    def test_megabytes(self):
        result = format_file_size(5 * 1024 * 1024)
        assert 'МБ' in result
    
    def test_gigabytes(self):
        result = format_file_size(2 * 1024 ** 3)
        assert 'ГБ' in result
    
    def test_zero(self):
        assert '0' in format_file_size(0)
    
    def test_negative(self):
        assert '0' in format_file_size(-100)


class TestGetMimeTypeIcon:
    """Тесты get_mime_type_icon."""
    
    def test_image(self):
        assert get_mime_type_icon('image/png') == 'bi-file-image'
        assert get_mime_type_icon('image/jpeg') == 'bi-file-image'
    
    def test_video(self):
        assert get_mime_type_icon('video/mp4') == 'bi-file-play'
    
    def test_audio(self):
        assert get_mime_type_icon('audio/mp3') == 'bi-file-music'
    
    def test_pdf(self):
        assert get_mime_type_icon('application/pdf') == 'bi-file-pdf'
    
    def test_zip(self):
        assert get_mime_type_icon('application/zip') == 'bi-file-zip'
    
    def test_unknown(self):
        assert get_mime_type_icon('application/octet-stream') == 'bi-file-earmark'
        assert get_mime_type_icon('') == 'bi-file-earmark'
        assert get_mime_type_icon(None) == 'bi-file-earmark'


class TestParseContentRange:
    """Тесты parse_content_range."""
    
    def test_valid_range(self):
        result = parse_content_range('bytes 0-499/1234')
        assert result == (0, 499, 1234)
    
    def test_unknown_total(self):
        result = parse_content_range('bytes 0-499/*')
        assert result == (0, 499, None)
    
    def test_invalid(self):
        assert parse_content_range('') is None
        assert parse_content_range(None) is None
        assert parse_content_range('invalid') is None


class TestGenerateUniqueFilename:
    """Тесты generate_unique_filename."""
    
    def test_no_conflict(self):
        existing = {'other.txt'}
        assert generate_unique_filename('file.txt', existing) == 'file.txt'
    
    def test_one_conflict(self):
        existing = {'file.txt'}
        result = generate_unique_filename('file.txt', existing)
        assert result == 'file (1).txt'
    
    def test_multiple_conflicts(self):
        existing = {'file.txt', 'file (1).txt', 'file (2).txt'}
        result = generate_unique_filename('file.txt', existing)
        assert result == 'file (3).txt'
    
    def test_no_extension(self):
        existing = {'README'}
        result = generate_unique_filename('README', existing)
        assert '(1)' in result
