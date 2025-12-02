"""Application configuration."""
import os
from datetime import timedelta

class Config:
    """Base configuration."""

    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')

    # Database
    DATABASE_URI = os.environ.get(
        'DATABASE_URI',
        'postgresql://webhook_user:password@localhost:5432/webhooks'
    )
    SQLALCHEMY_DATABASE_URI = DATABASE_URI
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

    # Base URL (for webhook URL generation)
    BASE_URL = os.environ.get('BASE_URL', 'http://localhost')

    # Frontend URL (for CORS)
    FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:3000')

    # Encryption key for API credentials (Fernet key)
    ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY')

    # SocketIO
    SOCKETIO_MESSAGE_QUEUE = os.environ.get('SOCKETIO_MESSAGE_QUEUE')  # Optional: Redis URL
