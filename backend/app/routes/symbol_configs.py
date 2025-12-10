"""Symbol configuration API routes."""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.symbol_config import SymbolConfig
import logging

bp = Blueprint('symbol_configs', __name__)
logger = logging.getLogger(__name__)


@bp.route('/', methods=['GET'])
@jwt_required()
def get_symbol_configs():
    """Get all symbol configs for the current user.
    
    Query params:
        broker: Filter by broker (optional)
    """
    user_id = get_jwt_identity()
    broker = request.args.get('broker')
    
    query = SymbolConfig.query.filter_by(user_id=user_id, is_active=True)
    
    if broker:
        query = query.filter_by(broker=broker)
    
    configs = query.order_by(SymbolConfig.symbol).all()
    
    return jsonify({
        'success': True,
        'configs': [c.to_dict() for c in configs]
    })


@bp.route('/', methods=['POST'])
@jwt_required()
def create_symbol_config():
    """Create a new symbol config.
    
    Body:
        symbol: Trading symbol (required)
        broker: Broker name (required)
        tp_count: Number of TP levels (1-3, default 1)
        sl_count: Number of SL levels (1-3, default 1)
        display_name: Optional display name
    """
    user_id = get_jwt_identity()
    data = request.get_json()
    
    # Validate required fields
    symbol = data.get('symbol', '').upper().strip()
    broker = data.get('broker', '').lower().strip()
    
    if not symbol:
        return jsonify({'success': False, 'error': 'Symbol is required'}), 400
    if not broker:
        return jsonify({'success': False, 'error': 'Broker is required'}), 400
    if broker not in ['oanda', 'blofin']:
        return jsonify({'success': False, 'error': 'Invalid broker'}), 400
    
    # Validate tp_count and sl_count
    tp_count = data.get('tp_count', 1)
    sl_count = data.get('sl_count', 1)
    
    try:
        tp_count = int(tp_count)
        sl_count = int(sl_count)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Invalid tp_count or sl_count'}), 400
    
    if tp_count < 1 or tp_count > 3:
        return jsonify({'success': False, 'error': 'tp_count must be 1, 2, or 3'}), 400
    if sl_count < 1 or sl_count > 3:
        return jsonify({'success': False, 'error': 'sl_count must be 1, 2, or 3'}), 400
    
    # Check if config already exists
    existing = SymbolConfig.query.filter_by(
        user_id=user_id,
        symbol=symbol,
        broker=broker
    ).first()
    
    if existing:
        return jsonify({
            'success': False, 
            'error': f'Config for {symbol} on {broker} already exists'
        }), 409
    
    # Create new config
    config = SymbolConfig(
        user_id=user_id,
        symbol=symbol,
        broker=broker,
        tp_count=tp_count,
        sl_count=sl_count,
        display_name=data.get('display_name'),
        is_active=True
    )
    
    db.session.add(config)
    db.session.commit()
    
    logger.info(f"Created symbol config: {symbol} ({broker}) for user {user_id}")
    
    return jsonify({
        'success': True,
        'config': config.to_dict()
    }), 201


@bp.route('/<int:config_id>', methods=['PUT'])
@jwt_required()
def update_symbol_config(config_id):
    """Update a symbol config.
    
    Body:
        tp_count: Number of TP levels (1-3)
        sl_count: Number of SL levels (1-3)
        display_name: Optional display name
    """
    user_id = get_jwt_identity()
    data = request.get_json()
    
    config = SymbolConfig.query.filter_by(
        id=config_id,
        user_id=user_id
    ).first()
    
    if not config:
        return jsonify({'success': False, 'error': 'Config not found'}), 404
    
    # Update fields
    if 'tp_count' in data:
        tp_count = int(data['tp_count'])
        if tp_count < 1 or tp_count > 3:
            return jsonify({'success': False, 'error': 'tp_count must be 1, 2, or 3'}), 400
        config.tp_count = tp_count
    
    if 'sl_count' in data:
        sl_count = int(data['sl_count'])
        if sl_count < 1 or sl_count > 3:
            return jsonify({'success': False, 'error': 'sl_count must be 1, 2, or 3'}), 400
        config.sl_count = sl_count
    
    if 'display_name' in data:
        config.display_name = data['display_name']
    
    db.session.commit()
    
    logger.info(f"Updated symbol config {config_id}: {config.symbol} ({config.broker})")
    
    return jsonify({
        'success': True,
        'config': config.to_dict()
    })


@bp.route('/<int:config_id>', methods=['DELETE'])
@jwt_required()
def delete_symbol_config(config_id):
    """Delete a symbol config."""
    user_id = get_jwt_identity()
    
    config = SymbolConfig.query.filter_by(
        id=config_id,
        user_id=user_id
    ).first()
    
    if not config:
        return jsonify({'success': False, 'error': 'Config not found'}), 404
    
    symbol = config.symbol
    broker = config.broker
    
    db.session.delete(config)
    db.session.commit()
    
    logger.info(f"Deleted symbol config {config_id}: {symbol} ({broker})")
    
    return jsonify({
        'success': True,
        'message': f'Config for {symbol} deleted'
    })


@bp.route('/bulk', methods=['POST'])
@jwt_required()
def bulk_create_configs():
    """Create multiple symbol configs at once.
    
    Body:
        configs: Array of config objects
    """
    user_id = get_jwt_identity()
    data = request.get_json()
    
    configs_data = data.get('configs', [])
    if not configs_data:
        return jsonify({'success': False, 'error': 'No configs provided'}), 400
    
    created = []
    errors = []
    
    for item in configs_data:
        symbol = item.get('symbol', '').upper().strip()
        broker = item.get('broker', '').lower().strip()
        
        if not symbol or not broker:
            errors.append(f"Missing symbol or broker")
            continue
        
        # Check if exists
        existing = SymbolConfig.query.filter_by(
            user_id=user_id,
            symbol=symbol,
            broker=broker
        ).first()
        
        if existing:
            errors.append(f"{symbol} ({broker}) already exists")
            continue
        
        config = SymbolConfig(
            user_id=user_id,
            symbol=symbol,
            broker=broker,
            tp_count=min(3, max(1, int(item.get('tp_count', 1)))),
            sl_count=min(3, max(1, int(item.get('sl_count', 1)))),
            display_name=item.get('display_name'),
            is_active=True
        )
        
        db.session.add(config)
        created.append(config)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'created': [c.to_dict() for c in created],
        'errors': errors
    })


@bp.route('/suggestions', methods=['GET'])
@jwt_required()
def get_symbol_suggestions():
    """Get symbol suggestions based on user's trade history.
    
    Returns symbols that have been traded but don't have a config yet.
    """
    from app.models.webhook_log import WebhookLog
    
    user_id = get_jwt_identity()
    
    # Get all unique symbol/broker combinations from webhook logs
    traded_symbols = db.session.query(
        WebhookLog.symbol,
        WebhookLog.broker
    ).filter(
        WebhookLog.user_id == user_id,
        WebhookLog.symbol.isnot(None),
        WebhookLog.symbol != '',
        WebhookLog.broker.isnot(None)
    ).distinct().all()
    
    # Get existing configs
    existing_configs = SymbolConfig.query.filter_by(
        user_id=user_id,
        is_active=True
    ).all()
    
    existing_set = {(c.symbol, c.broker) for c in existing_configs}
    
    # Filter to only symbols without configs
    suggestions = []
    for symbol, broker in traded_symbols:
        if symbol and broker and (symbol, broker) not in existing_set:
            suggestions.append({
                'symbol': symbol,
                'broker': broker
            })
    
    # Sort by symbol name
    suggestions.sort(key=lambda x: x['symbol'])
    
    return jsonify({
        'success': True,
        'suggestions': suggestions
    })
