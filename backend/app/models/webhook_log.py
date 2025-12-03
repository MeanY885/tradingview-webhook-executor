"""Webhook log model for tracking all incoming webhooks."""
from app.extensions import db
from datetime import datetime
import json


class WebhookLog(db.Model):
    """Log all incoming TradingView webhook requests."""
    __tablename__ = 'webhook_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Request data
    raw_payload = db.Column(db.Text, nullable=False)
    source_ip = db.Column(db.String(50))
    broker = db.Column(db.String(20), nullable=False)  # 'blofin' or 'oanda'

    # Parsed data
    symbol = db.Column(db.String(20))
    original_symbol = db.Column(db.String(20))
    action = db.Column(db.String(10))  # 'buy' or 'sell'
    order_type = db.Column(db.String(20))
    quantity = db.Column(db.Float)
    price = db.Column(db.Float)
    stop_loss = db.Column(db.Float)
    take_profit = db.Column(db.Float)
    trailing_stop_pct = db.Column(db.Float)
    leverage = db.Column(db.Float)  # Trading leverage (e.g., 5x, 10x)

    # Additional metadata (stored as JSON for flexibility)
    metadata_json = db.Column(db.Text)  # Stores TradingView metadata, alert_message_params, etc.

    # Execution status
    status = db.Column(db.String(20), nullable=False)  # 'success', 'failed', 'invalid', 'test_success'
    broker_order_id = db.Column(db.String(50))
    client_order_id = db.Column(db.String(32))
    error_message = db.Column(db.Text)

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', back_populates='webhook_logs')

    def to_dict(self):
        """Serialize webhook log to dict."""
        # Parse metadata_json if present
        metadata = {}
        if self.metadata_json:
            try:
                metadata = json.loads(self.metadata_json)
            except (json.JSONDecodeError, TypeError):
                metadata = {}

        return {
            'id': self.id,
            'user_id': self.user_id,
            'timestamp': self.timestamp.isoformat(),
            'broker': self.broker,
            'symbol': self.symbol,
            'original_symbol': self.original_symbol,
            'action': self.action,
            'order_type': self.order_type,
            'quantity': self.quantity,
            'price': self.price,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'leverage': self.leverage,
            'metadata': metadata,
            'status': self.status,
            'broker_order_id': self.broker_order_id,
            'client_order_id': self.client_order_id,
            'error_message': self.error_message,
            'raw_payload': self.raw_payload,  # Include raw payload for debugging
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
