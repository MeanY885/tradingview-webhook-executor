"""Webhook logs routes for frontend."""
import json
import logging
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.webhook_log import WebhookLog
from app.extensions import db
from app.services.tradingview import TradingViewAlertParser
from app.services.symbol_converter import SymbolConverter
from app.services.webhook_normalizer import WebhookNormalizer
from app.services.trade_grouping import TradeGroupingService
from app.services.pnl_calculator import PnLCalculator
from sqlalchemy import desc, func

logger = logging.getLogger(__name__)

bp = Blueprint('webhook_logs', __name__, url_prefix='/api/webhook-logs')


@bp.route('', methods=['GET'])
@jwt_required()
def get_webhook_logs():
    """Get webhook logs for current user with filtering."""
    user_id = int(get_jwt_identity())  # Convert string back to int

    # Query params
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    broker = request.args.get('broker')
    status = request.args.get('status')
    symbol = request.args.get('symbol')

    # Build query
    query = WebhookLog.query.filter_by(user_id=user_id)

    if broker:
        query = query.filter_by(broker=broker)
    if status:
        query = query.filter_by(status=status)
    if symbol:
        query = query.filter(WebhookLog.symbol.ilike(f'%{symbol}%'))

    # Paginate
    pagination = query.order_by(desc(WebhookLog.timestamp)).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )

    return jsonify({
        'logs': [log.to_dict() for log in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages
    })


@bp.route('/stats', methods=['GET'])
@jwt_required()
def get_webhook_stats():
    """Get statistics for current user."""
    user_id = int(get_jwt_identity())  # Convert string back to int

    # Count by status
    stats = db.session.query(
        WebhookLog.status,
        func.count(WebhookLog.id).label('count')
    ).filter_by(user_id=user_id).group_by(WebhookLog.status).all()

    return jsonify({
        'by_status': {stat.status: stat.count for stat in stats}
    })


@bp.route('/<int:log_id>', methods=['DELETE'])
@jwt_required()
def delete_webhook_log(log_id):
    """Delete a webhook log entry."""
    user_id = int(get_jwt_identity())

    # Find the log entry
    log = WebhookLog.query.filter_by(id=log_id, user_id=user_id).first()

    if not log:
        return jsonify({'success': False, 'error': 'Webhook log not found'}), 404

    # Delete the log
    db.session.delete(log)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Webhook log deleted successfully'
    })



@bp.route('/<int:log_id>/reprocess', methods=['POST'])
@jwt_required()
def reprocess_webhook_log(log_id):
    """
    Reprocess a webhook log entry with the current parser.
    
    Useful for re-parsing webhooks that failed due to parser bugs
    that have since been fixed.
    """
    user_id = int(get_jwt_identity())

    # Find the log entry
    log = WebhookLog.query.filter_by(id=log_id, user_id=user_id).first()

    if not log:
        return jsonify({'success': False, 'error': 'Webhook log not found'}), 404

    if not log.raw_payload:
        return jsonify({'success': False, 'error': 'No raw payload to reprocess'}), 400

    try:
        # Parse the raw payload with current parser
        parser = TradingViewAlertParser()
        params = parser.parse_alert(log.raw_payload)
        
        # Convert symbol to broker format
        original_symbol = params['symbol']
        params['symbol'] = SymbolConverter.normalize_symbol(original_symbol, log.broker)
        
        # Validate params
        is_valid, error_msg = parser.validate_params(params)
        if not is_valid:
            return jsonify({
                'success': False,
                'error': f'Validation failed: {error_msg}',
                'parsed': params
            }), 400
        
        # Parse raw payload as dict for normalization
        raw_payload_dict = {}
        try:
            raw_payload_dict = json.loads(log.raw_payload)
        except (json.JSONDecodeError, TypeError):
            raw_payload_dict = {}
        
        # Normalize the webhook
        normalized = WebhookNormalizer.normalize(raw_payload_dict)
        
        # Determine trade group
        result = TradeGroupingService.determine_trade_group_from_normalized(
            user_id=user_id,
            normalized=normalized
        )
        
        # Update log entry with parsed data
        log.symbol = params['symbol']
        log.original_symbol = original_symbol
        log.action = params['action']
        # Sanitize order_type - if it's a TradingView placeholder, default to 'market'
        order_type = params['order_type']
        if order_type and (order_type.startswith('{{') or len(order_type) > 20):
            order_type = 'market'
        log.order_type = order_type
        log.quantity = params['quantity']
        log.price = params.get('price')
        log.stop_loss = normalized.stop_loss_price or params.get('stop_loss')
        log.take_profit = params.get('take_profit')
        log.leverage = normalized.leverage or params.get('leverage')
        log.trade_group_id = result.trade_group_id
        log.trade_direction = result.trade_direction
        
        # TP tracking fields
        log.tp_level = normalized.alert_type if normalized.alert_type != 'UNKNOWN' else None
        log.position_size_after = normalized.position_size
        
        # Entry price
        if result.is_new_group:
            log.entry_price = normalized.order_price
        else:
            log.entry_price = result.entry_price
        
        # SL/TP tracking
        log.current_stop_loss = normalized.stop_loss_price
        log.current_take_profit = normalized.take_profit_price
        log.exit_trail_price = normalized.exit_trail_price
        log.exit_trail_offset = normalized.exit_trail_offset
        
        # Update metadata_json with fresh parsed data
        metadata = params.get('metadata', {})
        if metadata:
            try:
                log.metadata_json = json.dumps(metadata)
            except (TypeError, ValueError):
                pass
        
        # Update status based on test_mode
        if params.get('test_mode', False):
            log.status = 'test_success'
            log.error_message = 'Reprocessed: Test mode - no actual trade executed'
        else:
            # Keep as reprocessed if it was a parse error, otherwise keep original status
            if log.status == 'parse_error':
                log.status = 'reprocessed'
                log.error_message = 'Reprocessed successfully - original was parse_error'
        
        db.session.commit()
        
        logger.info(f"Reprocessed webhook log {log_id} for user {user_id}")
        
        return jsonify({
            'success': True,
            'message': 'Webhook reprocessed successfully',
            'log': log.to_dict()
        })
        
    except ValueError as e:
        logger.warning(f"Reprocess failed for log {log_id}: {e}")
        return jsonify({
            'success': False,
            'error': f'Parse error: {str(e)}'
        }), 400
    except Exception as e:
        logger.error(f"Reprocess error for log {log_id}: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Internal error: {str(e)}'
        }), 500


@bp.route('/reprocess-all-errors', methods=['POST'])
@jwt_required()
def reprocess_all_parse_errors():
    """
    Reprocess all webhook logs with parse_error status for the current user.
    
    Returns summary of results.
    """
    user_id = int(get_jwt_identity())
    
    # Find all parse_error logs for this user
    error_logs = WebhookLog.query.filter_by(
        user_id=user_id,
        status='parse_error'
    ).all()
    
    if not error_logs:
        return jsonify({
            'success': True,
            'message': 'No parse errors to reprocess',
            'total': 0,
            'succeeded': 0,
            'failed': 0
        })
    
    succeeded = 0
    failed = 0
    failures = []
    
    parser = TradingViewAlertParser()
    
    for log in error_logs:
        try:
            if not log.raw_payload:
                failed += 1
                failures.append({'id': log.id, 'error': 'No raw payload'})
                continue
            
            # Parse the raw payload
            params = parser.parse_alert(log.raw_payload)
            
            # Convert symbol
            original_symbol = params['symbol']
            params['symbol'] = SymbolConverter.normalize_symbol(original_symbol, log.broker)
            
            # Validate
            is_valid, error_msg = parser.validate_params(params)
            if not is_valid:
                failed += 1
                failures.append({'id': log.id, 'error': error_msg})
                continue
            
            # Parse raw payload as dict
            raw_payload_dict = {}
            try:
                raw_payload_dict = json.loads(log.raw_payload)
            except (json.JSONDecodeError, TypeError):
                raw_payload_dict = {}
            
            # Normalize
            normalized = WebhookNormalizer.normalize(raw_payload_dict)
            
            # Determine trade group
            result = TradeGroupingService.determine_trade_group_from_normalized(
                user_id=user_id,
                normalized=normalized
            )
            
            # Update log
            log.symbol = params['symbol']
            log.original_symbol = original_symbol
            log.action = params['action']
            # Sanitize order_type - if it's a TradingView placeholder, default to 'market'
            order_type = params['order_type']
            if order_type and (order_type.startswith('{{') or len(order_type) > 20):
                order_type = 'market'
            log.order_type = order_type
            log.quantity = params['quantity']
            log.price = params.get('price')
            log.stop_loss = normalized.stop_loss_price or params.get('stop_loss')
            log.leverage = normalized.leverage or params.get('leverage')
            log.trade_group_id = result.trade_group_id
            log.trade_direction = result.trade_direction
            log.tp_level = normalized.alert_type if normalized.alert_type != 'UNKNOWN' else None
            log.position_size_after = normalized.position_size
            log.current_stop_loss = normalized.stop_loss_price
            log.current_take_profit = normalized.take_profit_price
            log.exit_trail_price = normalized.exit_trail_price
            log.exit_trail_offset = normalized.exit_trail_offset
            
            if result.is_new_group:
                log.entry_price = normalized.order_price
            else:
                log.entry_price = result.entry_price
            
            if params.get('test_mode', False):
                log.status = 'test_success'
                log.error_message = 'Reprocessed: Test mode'
            else:
                log.status = 'reprocessed'
                log.error_message = 'Reprocessed successfully'
            
            succeeded += 1
            
        except Exception as e:
            failed += 1
            failures.append({'id': log.id, 'error': str(e)})
    
    db.session.commit()
    
    logger.info(f"Reprocessed {succeeded}/{len(error_logs)} parse errors for user {user_id}")
    
    return jsonify({
        'success': True,
        'message': f'Reprocessed {succeeded} of {len(error_logs)} webhooks',
        'total': len(error_logs),
        'succeeded': succeeded,
        'failed': failed,
        'failures': failures[:10]  # Limit to first 10 failures
    })
