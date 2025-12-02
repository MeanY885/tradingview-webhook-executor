"""User credentials model with encrypted API keys."""
from app.extensions import db
from datetime import datetime


class UserCredentials(db.Model):
    """Encrypted API credentials per user."""
    __tablename__ = 'user_credentials'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    broker = db.Column(db.String(20), nullable=False)  # 'blofin' or 'oanda'

    # Encrypted fields (stored as text)
    api_key_encrypted = db.Column(db.Text, nullable=False)
    secret_key_encrypted = db.Column(db.Text)       # Blofin only
    passphrase_encrypted = db.Column(db.Text)       # Blofin only
    account_id_encrypted = db.Column(db.Text)       # Oanda only

    # Metadata
    is_active = db.Column(db.Boolean, default=True)
    label = db.Column(db.String(100))  # e.g., "Main Account"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship('User', back_populates='credentials')

    def to_dict(self, include_decrypted=False):
        """Serialize credentials (never include decrypted keys in normal responses)."""
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'broker': self.broker,
            'label': self.label,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat()
        }
        # Only include decrypted keys when explicitly requested (e.g., for trading)
        # Never send decrypted keys to frontend
        return data
