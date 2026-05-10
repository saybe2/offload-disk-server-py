# Cloud Storage

Веб-приложение для безопасного облачного хранения файлов с шифрованием и хранением в Discord.

## Описание проекта

Cloud Storage — это веб-приложение на Flask, которое позволяет пользователям загружать файлы в зашифрованном виде, используя Discord как бесплатное облачное хранилище. Все файлы шифруются алгоритмом AES-256-GCM перед загрузкой, обеспечивая полную конфиденциальность данных.

### Основные возможности

- **Регистрация и авторизация** пользователей
- **Загрузка файлов** с автоматическим шифрованием
- **Скачивание файлов** с расшифровкой на лету
- **Организация файлов** в папки с неограниченной вложенностью
- **REST API** для всех операций
- **Адаптивный интерфейс** на Bootstrap 5

## Технологии

| Технология | Назначение |
|------------|------------|
| **Flask 3.0** | Веб-фреймворк |
| **SQLAlchemy** | ORM для работы с БД |
| **Flask-Login** | Управление сессиями |
| **SQLite** | База данных |
| **Bootstrap 5** | UI фреймворк |
| **AES-256-GCM** | Шифрование файлов |
| **Discord API** | Хранение файлов |

## Структура проекта

```
offload-disk-server-py/
├── app.py                  # Точка входа приложения
├── config.py               # Конфигурация
├── requirements.txt        # Зависимости Python
├── models/
│   ├── __init__.py         # Инициализация БД
│   ├── user.py             # Модель пользователя
│   ├── file.py             # Модель файла
│   └── folder.py           # Модель папки
├── routes/
│   ├── __init__.py
│   ├── auth.py             # Авторизация
│   ├── api.py              # REST API
│   └── main.py             # Основные страницы
├── services/
│   ├── __init__.py
│   ├── crypto.py           # Шифрование AES-256-GCM
│   ├── discord.py          # Работа с Discord API
│   └── storage.py          # Управление хранилищем
├── templates/
│   ├── base.html           # Базовый шаблон
│   ├── login.html          # Страница входа
│   ├── register.html       # Страница регистрации
│   ├── app.html            # Файловый менеджер
│   └── admin.html          # Панель администратора
└── static/
    └── js/
        └── app.js          # Клиентский JavaScript
```

## Установка и запуск

### 1. Клонирование репозитория

```bash
git clone https://github.com/saybe2/offload-disk-server-py.git
cd offload-disk-server-py
```

### 2. Создание виртуального окружения

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Настройка конфигурации

```bash
cp .env.example .env
```

Отредактируйте файл `.env`:

```env
SECRET_KEY=ваш-секретный-ключ
MASTER_KEY=32-символьный-ключ-шифрования
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

### 5. Запуск приложения

```bash
python app.py
```

Приложение будет доступно по адресу: http://localhost:5000

### Учётные данные по умолчанию

При первом запуске создаётся администратор:
- **Логин:** admin
- **Пароль:** admin

## API Endpoints

### Авторизация

| Метод | URL | Описание |
|-------|-----|----------|
| POST | `/auth/register` | Регистрация |
| POST | `/auth/login` | Вход |
| GET/POST | `/auth/logout` | Выход |
| GET | `/auth/me` | Информация о пользователе |
| POST | `/auth/change-password` | Смена пароля |

### Файлы

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/api/files` | Список файлов |
| GET | `/api/files/<id>` | Информация о файле |
| POST | `/api/files/upload` | Загрузка файла |
| GET | `/api/files/<id>/download` | Скачивание |
| DELETE | `/api/files/<id>` | Удаление |
| PATCH | `/api/files/<id>/rename` | Переименование |
| PATCH | `/api/files/<id>/move` | Перемещение |

### Папки

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/api/folders` | Список папок |
| POST | `/api/folders` | Создание папки |
| GET | `/api/folders/<id>` | Информация о папке |
| DELETE | `/api/folders/<id>` | Удаление |
| PATCH | `/api/folders/<id>/rename` | Переименование |

## Безопасность

- **Шифрование AES-256-GCM** — все файлы шифруются перед загрузкой
- **Хэширование паролей** — bcrypt через Werkzeug
- **Защита сессий** — Flask-Login с secure cookies
- **Валидация данных** — на сервере и клиенте

## Хостинг

Для развёртывания в production рекомендуется:

1. Использовать Gunicorn как WSGI сервер
2. Настроить Nginx как reverse proxy
3. Использовать PostgreSQL вместо SQLite

```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## Лицензия

MIT License

## Авторы

Проект выполнен в рамках курса Web-разработки Яндекс.Лицея.
