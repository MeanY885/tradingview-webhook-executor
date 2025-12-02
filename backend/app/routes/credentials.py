"""Credentials management routes."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.user_credentials import UserCredentials
from app.services.encryption import encryption_service

bp = Blueprint('credentials', __name__, url_prefix='/api/credentials')


@bp.route('', methods=['GET'])
@jwt_required()
def get_credentials():
    """Get all credentials for current user."""
    user_id = get_jwt_identity()
    credentials = UserCredentials.query.filter_by(user_id=user_id).all()
    return jsonify([c.to_dict() for c in credentials])


@bp.route('', methods=['POST'])
@jwt_required()
def create_credentials():
    """Create new credential set."""
    user_id = get_jwt_identity()
    data = request.get_json()

    broker = data.get('broker')
    if broker not in ['blofin', 'oanda']:
        return jsonify({'error': 'Invalid broker'}), 400

    # Encrypt fields
    if broker == 'blofin':
        if not all([data.get('api_key'), data.get('secret_key'), data.get('passphrase')]):
            return jsonify({'error': 'Blofin requires api_key, secret_key, and passphrase'}), 400

        cred = UserCredentials(
            user_id=user_id,
            broker=broker,
            api_key_encrypted=encryption_service.encrypt(data['api_key']),
            secret_key_encrypted=encryption_service.encrypt(data['secret_key']),
            passphrase_encrypted=encryption_service.encrypt(data['passphrase']),
            label=data.get('label', 'Default')
        )

    elif broker == 'oanda':
        if not all([data.get('api_key'), data.get('account_id')]):
            return jsonify({'error': 'Oanda requires api_key and account_id'}), 400

        cred = UserCredentials(
            user_id=user_id,
            broker=broker,
            api_key_encrypted=encryption_service.encrypt(data['api_key']),
            account_id_encrypted=encryption_service.encrypt(data['account_id']),
            label=data.get('label', 'Default')
        )

    db.session.add(cred)
    db.session.commit()

    return jsonify(cred.to_dict()), 201


@bp.route('/<int:cred_id>', methods=['PUT'])
@jwt_required()
def update_credentials(cred_id):
    """Update credential set."""
    user_id = get_jwt_identity()
    cred = UserCredentials.query.filter_by(id=cred_id, user_id=user_id).first()

    if not cred:
        return jsonify({'error': 'Credentials not found'}), 404

    data = request.get_json()

    # Update encrypted fields if provided
    if 'api_key' in data:
        cred.api_key_encrypted = encryption_service.encrypt(data['api_key'])
    if 'secret_key' in data:
        cred.secret_key_encrypted = encryption_service.encrypt(data['secret_key'])
    if 'passphrase' in data:
        cred.passphrase_encrypted = encryption_service.encrypt(data['passphrase'])
    if 'account_id' in data:
        cred.account_id_encrypted = encryption_service.encrypt(data['account_id'])

    if 'label' in data:
        cred.label = data['label']
    if 'is_active' in data:
        cred.is_active = data['is_active']

    db.session.commit()
    return jsonify(cred.to_dict())


@bp.route('/<int:cred_id>', methods=['DELETE'])
@jwt_required()
def delete_credentials(cred_id):
    """Delete credential set."""
    user_id = get_jwt_identity()
    cred = UserCredentials.query.filter_by(id=cred_id, user_id=user_id).first()

    if not cred:
        return jsonify({'error': 'Credentials not found'}), 404

    db.session.delete(cred)
    db.session.commit()
    return '', 204
