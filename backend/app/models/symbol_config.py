"""Symbol configuration model for user-defined TP/SL settings."""
from app.extensions import db
from datetime import datetime


class SymbolConfig(db.Model):
    """User-defined configuration for trading symbols.
    
    Allows users to configure how many TP and SL levels each symbol has,
    which determines when a trade is considered closed.
    """
    __tablename__ = 'symbol_configs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Symbol identification
    symbol = db.Column(db.String(20), nullable=False)  # e.g., 'EURUSD', 'BTCUSDT'
    broker = db.Column(db.String(20), nullable=False)  # 'oanda', 'blofin'
    
    # TP/SL configuration
    tp_count = db.Column(db.Integer, default=1)  # Number of TP levels (1, 2, or 3)
    sl_count = db.Column(db.Integer, default=1)  # Number of SL levels (1, 2, or 3)
    
    # Optional: custom display name
    display_name = db.Column(db.String(50))  # e.g., 'Euro/USD'
    
    # Metadata
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship('User', back_populates='symbol_configs')

    # Unique constraint: one config per user/symbol/broker combination
    __table_args__ = (
        db.UniqueConstraint('user_id', 'symbol', 'broker', name='uq_user_symbol_broker'),
    )

    def to_dict(self):
        """Serialize symbol config."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'symbol': self.symbol,
            'broker': self.broker,
            'tp_count': self.tp_count,
            'sl_count': self.sl_count,
            'display_name': self.display_name,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
    
    @staticmethod
    def get_config(user_id: int, symbol: str, broker: str) -> 'SymbolConfig':
        """Get symbol config for a user, or return default values.
        
        Args:
            user_id: User ID
            symbol: Trading symbol (e.g., 'EUR_USD')
            broker: Broker name (e.g., 'oanda')
            
        Returns:
            SymbolConfig instance (from DB or default)
        """
        config = SymbolConfig.query.filter_by(
            user_id=user_id,
            symbol=symbol,
            broker=broker,
            is_active=True
        ).first()
        
        if config:
            return config
        
        # Return a default config (not saved to DB)
        return SymbolConfig(
            user_id=user_id,
            symbol=symbol,
            broker=broker,
            tp_count=1,  # Default: single TP
            sl_count=1,  # Default: single SL
            is_active=True
        )
