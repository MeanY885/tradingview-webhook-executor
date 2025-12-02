"""User model with authentication."""
from app.extensions import db
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime


class User(db.Model):
    """User model with authentication and webhook token."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    webhook_token = db.Column(db.String(64), unique=True, nullable=False)
    role = db.Column(db.String(20), default='user')  # 'user' or 'admin'
    is_active = db.Column(db.Boolean, default=True)

    # IP Whitelist for webhook security
    webhook_ip_whitelist_enabled = db.Column(db.Boolean, default=False)
    webhook_ip_whitelist = db.Column(db.Text, default='[]')  # JSON array of allowed IPs

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    credentials = db.relationship('UserCredentials', back_populates='user', cascade='all, delete-orphan')
    webhook_logs = db.relationship('WebhookLog', back_populates='user')

    def set_password(self, password):
        """Hash and set password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify password."""
        return check_password_hash(self.password_hash, password)

    def to_dict(self, include_webhook_urls=False):
        """Serialize user to dict."""
        from app.config import Config

        data = {
            'id': self.id,
            'email': self.email,
            'username': self.username,
            'role': self.role,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat()
        }

        if include_webhook_urls:
            # Include webhook URLs for settings page
            base_url = Config.BASE_URL or 'https://your-domain.com'
            data['webhook_urls'] = {
                'blofin': f"{base_url}/blofin/{self.webhook_token}",
                'oanda': f"{base_url}/oanda/{self.webhook_token}"
            }

        return data

    @staticmethod
    def generate_webhook_token():
        """Generate unique webhook token."""
        import secrets
        return secrets.token_urlsafe(32)

    def get_webhook_ip_whitelist(self):
        """Get IP whitelist as Python list."""
        import json
        try:
            return json.loads(self.webhook_ip_whitelist or '[]')
        except (json.JSONDecodeError, TypeError):
            return []

    def set_webhook_ip_whitelist(self, ip_list):
        """Set IP whitelist from Python list."""
        import json
        self.webhook_ip_whitelist = json.dumps(ip_list)

    def is_ip_whitelisted(self, ip_address):
        """Check if IP address is whitelisted (or whitelist is disabled)."""
        if not self.webhook_ip_whitelist_enabled:
            return True  # Whitelist disabled, allow all IPs

        whitelist = self.get_webhook_ip_whitelist()
        if not whitelist:
            return True  # Empty whitelist, allow all IPs

        # Support both single IPs and CIDR notation
        from ipaddress import ip_address as parse_ip, ip_network
        try:
            request_ip = parse_ip(ip_address)
            for allowed in whitelist:
                # Check if it's a CIDR range
                if '/' in allowed:
                    if request_ip in ip_network(allowed, strict=False):
                        return True
                # Check exact IP match
                elif request_ip == parse_ip(allowed):
                    return True
            return False
        except ValueError:
            return False  # Invalid IP format
