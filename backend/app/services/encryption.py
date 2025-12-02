"""Encryption service for API credentials."""
from cryptography.fernet import Fernet
from app.config import Config


class EncryptionService:
    """Encrypt/decrypt sensitive data using Fernet (symmetric encryption)."""

    def __init__(self):
        key = Config.ENCRYPTION_KEY
        if not key:
            raise ValueError("ENCRYPTION_KEY not configured")
        self.cipher = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt string and return base64-encoded ciphertext."""
        if not plaintext:
            return None
        return self.cipher.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt base64-encoded ciphertext and return plaintext."""
        if not ciphertext:
            return None
        return self.cipher.decrypt(ciphertext.encode()).decode()


# Singleton instance
encryption_service = EncryptionService()
