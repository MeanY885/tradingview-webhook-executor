"""Authentication routes."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity
)
from app.extensions import db
from app.models.user import User

bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@bp.route('/register', methods=['POST'])
def register():
    """Register new user."""
    data = request.get_json()

    # Validate input
    if not data.get('email') or not data.get('password') or not data.get('username'):
        return jsonify({'error': 'Email, username, and password required'}), 400

    # Check if user exists
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already registered'}), 400

    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already taken'}), 400

    # Create user
    user = User(
        email=data['email'],
        username=data['username'],
        webhook_token=User.generate_webhook_token(),
        role='user'  # First user should be made admin manually
    )
    user.set_password(data['password'])

    db.session.add(user)
    db.session.commit()

    return jsonify({
        'message': 'User registered successfully',
        'user': user.to_dict()
    }), 201


@bp.route('/login', methods=['POST'])
def login():
    """Login and get JWT tokens."""
    data = request.get_json()

    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400

    # Find user
    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid credentials'}), 401

    if not user.is_active:
        return jsonify({'error': 'Account disabled'}), 403

    # Create tokens (identity must be string)
    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    return jsonify({
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': user.to_dict(include_webhook_urls=True)
    })


@bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """Get current user info with webhook URLs."""
    user_id = int(get_jwt_identity())  # Convert string back to int
    user = User.query.get(user_id)

    if not user:
        return jsonify({'error': 'User not found'}), 404

    return jsonify(user.to_dict(include_webhook_urls=True))


@bp.route('/regenerate-webhook-token', methods=['POST'])
@jwt_required()
def regenerate_webhook_token():
    """Regenerate user's webhook token (invalidates old URLs)."""
    user_id = int(get_jwt_identity())  # Convert string back to int
    user = User.query.get(user_id)

    if not user:
        return jsonify({'error': 'User not found'}), 404

    user.webhook_token = User.generate_webhook_token()
    db.session.commit()

    return jsonify({
        'message': 'Webhook token regenerated',
        'user': user.to_dict(include_webhook_urls=True)
    })


@bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Refresh access token."""
    user_id = get_jwt_identity()  # Already a string from the refresh token
    access_token = create_access_token(identity=user_id)  # Keep as string
    return jsonify({'access_token': access_token})


@bp.route('/webhook-ip-whitelist', methods=['GET'])
@jwt_required()
def get_webhook_ip_whitelist():
    """Get current IP whitelist settings."""
    user_id = int(get_jwt_identity())  # Convert string back to int
    user = User.query.get(user_id)

    if not user:
        return jsonify({'error': 'User not found'}), 404

    return jsonify({
        'enabled': user.webhook_ip_whitelist_enabled,
        'whitelist': user.get_webhook_ip_whitelist(),
        'tradingview_ips': [
            '52.89.214.238',
            '34.212.75.30',
            '54.218.53.128',
            '52.32.178.7'
        ]
    })


@bp.route('/webhook-ip-whitelist', methods=['PUT'])
@jwt_required()
def update_webhook_ip_whitelist():
    """Update IP whitelist settings."""
    user_id = int(get_jwt_identity())  # Convert string back to int
    user = User.query.get(user_id)

    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json()

    # Update enabled status
    if 'enabled' in data:
        user.webhook_ip_whitelist_enabled = bool(data['enabled'])

    # Update whitelist
    if 'whitelist' in data:
        whitelist = data['whitelist']
        if not isinstance(whitelist, list):
            return jsonify({'error': 'Whitelist must be an array'}), 400

        # Validate IP addresses
        from ipaddress import ip_address, ip_network
        for ip_entry in whitelist:
            try:
                if '/' in ip_entry:
                    ip_network(ip_entry, strict=False)
                else:
                    ip_address(ip_entry)
            except ValueError:
                return jsonify({'error': f'Invalid IP address or CIDR: {ip_entry}'}), 400

        user.set_webhook_ip_whitelist(whitelist)

    db.session.commit()

    return jsonify({
        'message': 'IP whitelist updated successfully',
        'enabled': user.webhook_ip_whitelist_enabled,
        'whitelist': user.get_webhook_ip_whitelist()
    })


@bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """
    Change user password.
    
    Request body:
    - current_password: Required for self-change
    - new_password: New password (min 8 chars)
    - user_id: Optional, for admin changing another user's password
    
    Returns:
    - 200: Password changed successfully
    - 400: Validation error (password too short)
    - 401: Current password incorrect
    - 403: Not authorized to change this user's password
    """
    current_user_id = int(get_jwt_identity())
    current_user = User.query.get(current_user_id)
    
    if not current_user:
        return jsonify({'error': 'User not found'}), 404
    
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body required'}), 400
    
    new_password = data.get('new_password')
    target_user_id = data.get('user_id')
    current_password = data.get('current_password')
    
    # Validate new password is provided
    if not new_password:
        return jsonify({'error': 'New password required'}), 400
    
    # Validate minimum password length (8 characters)
    if len(new_password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400
    
    # Determine target user
    if target_user_id and target_user_id != current_user_id:
        # Changing another user's password - requires admin role
        if current_user.role != 'admin':
            return jsonify({'error': 'Not authorized to change this password'}), 403
        
        target_user = User.query.get(target_user_id)
        if not target_user:
            return jsonify({'error': 'Target user not found'}), 404
    else:
        # Changing own password - requires current password verification
        target_user = current_user
        
        if not current_password:
            return jsonify({'error': 'Current password required'}), 400
        
        if not current_user.check_password(current_password):
            return jsonify({'error': 'Invalid credentials'}), 401
    
    # Set new password (uses bcrypt via werkzeug)
    target_user.set_password(new_password)
    db.session.commit()
    
    return jsonify({'message': 'Password changed successfully'}), 200
