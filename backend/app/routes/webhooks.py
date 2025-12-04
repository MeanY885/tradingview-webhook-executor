"""TradingView webhook endpoints for trade execution."""
from flask import Blueprint, request, jsonify
from app.extensions import db
from app.models.user import User
from app.models.webhook_log import WebhookLog
from app.models.user_credentials import UserCredentials
from app.services.tradingview import TradingViewAlertParser
from app.services.symbol_converter import SymbolConverter
from app.services.blofin import BlofinClient
from app.services.oanda import OandaClient
from app.services.encryption import encryption_service
from app.services.websocket import broadcast_webhook_event
from app.services.trade_grouping import TradeGroupingService
from app.services.webhook_normalizer import WebhookNormalizer, AlertType
from app.services.pnl_calculator import PnLCalculator
import logging
import uuid

bp = Blueprint('webhooks', __name__)
logger = logging.getLogger(__name__)


@bp.route('/blofin/<webhook_identifier>', methods=['POST'])
def tradingview_blofin_webhook(webhook_identifier):
    """Receive TradingView webhook for Blofin (crypto trading).

    Accepts either username or webhook token.
    Examples:
    - /blofin/chrise885
    - /blofin/a8f3b2c1d4e5f6a7b8c9d0e1f2a3b4c5
    """
    return _process_webhook('blofin', webhook_identifier)


@bp.route('/oanda/<webhook_identifier>', methods=['POST'])
def tradingview_oanda_webhook(webhook_identifier):
    """Receive TradingView webhook for Oanda (forex trading).

    Accepts either username or webhook token.
    Examples:
    - /oanda/chrise885
    - /oanda/a8f3b2c1d4e5f6a7b8c9d0e1f2a3b4c5
    """
    return _process_webhook('oanda', webhook_identifier)


def _process_webhook(broker: str, webhook_identifier: str):
    """
    Common webhook processing logic.

    Args:
        broker: 'blofin' or 'oanda'
        webhook_identifier: User's webhook token OR username from URL

    Returns:
        JSON response with success/error status
    """
    log_entry = None
    user = None
    raw_payload = None

    try:
        # 1. Authenticate via webhook identifier (username or token) in URL
        # Try username first (more user-friendly), then fall back to token
        user = User.query.filter_by(username=webhook_identifier, is_active=True).first()
        if not user:
            # Fall back to token-based lookup (backwards compatibility)
            user = User.query.filter_by(webhook_token=webhook_identifier, is_active=True).first()

        if not user:
            logger.warning(f"Invalid webhook identifier: {webhook_identifier[:8]}... from IP: {request.remote_addr}")
            return jsonify({'success': False, 'error': 'Invalid webhook URL'}), 401

        # 2. Check IP whitelist
        client_ip = request.headers.get('X-Real-IP') or request.headers.get('X-Forwarded-For', '').split(',')[0].strip() or request.remote_addr
        if not user.is_ip_whitelisted(client_ip):
            logger.warning(f"IP {client_ip} not whitelisted for user {user.id}")
            return jsonify({'success': False, 'error': 'IP address not authorized'}), 403

        # 3. Get raw payload - ALWAYS capture this first
        raw_payload = request.get_data(as_text=True)
        logger.info(f"Received webhook for user {user.id} ({broker}) from IP {client_ip}: {raw_payload[:200]}")

        # 4. Parse alert - use lenient mode to capture unknown formats
        parser = TradingViewAlertParser()
        params = parser.parse_alert(raw_payload)

        # 4. Convert symbol to broker format
        original_symbol = params['symbol']
        params['symbol'] = SymbolConverter.normalize_symbol(original_symbol, broker)

        logger.info(f"Parsed alert: {params['action']} {params['quantity']} {params['symbol']} (original: {original_symbol})")

        # 5. Validate params
        is_valid, error_msg = parser.validate_params(params)
        if not is_valid:
            log_entry = _create_log_entry(
                user.id, raw_payload, broker, params,
                original_symbol, status='invalid', error=error_msg
            )
            broadcast_webhook_event(user.id, log_entry)
            logger.warning(f"Invalid alert params: {error_msg}")
            return jsonify({'success': False, 'error': error_msg}), 400

        # 6. Create pending log entry
        log_entry = _create_log_entry(
            user.id, raw_payload, broker, params,
            original_symbol, status='pending'
        )

        # 7. Check for test mode
        if params.get('test_mode', False):
            logger.info(f"Test mode enabled - skipping trade execution for user {user.id}")
            log_entry.status = 'test_success'
            log_entry.broker_order_id = f'TEST-{uuid.uuid4().hex[:8].upper()}'
            log_entry.error_message = 'Test mode - no actual trade executed'
            db.session.commit()
            broadcast_webhook_event(user.id, log_entry)
            return jsonify({
                'success': True,
                'test_mode': True,
                'order_id': log_entry.broker_order_id,
                'webhook_log_id': log_entry.id,
                'message': 'Test alert received successfully - no trade executed'
            })

        # 8. Get user credentials
        cred = UserCredentials.query.filter_by(
            user_id=user.id,
            broker=broker,
            is_active=True
        ).first()

        if not cred:
            log_entry.status = 'failed'
            log_entry.error_message = f'No active {broker} credentials found'
            db.session.commit()
            broadcast_webhook_event(user.id, log_entry)
            logger.error(f"No credentials found for user {user.id} on {broker}")
            return jsonify({'success': False, 'error': 'Credentials not configured'}), 400

        # 9. Execute trade
        if broker == 'blofin':
            result = _execute_blofin_trade(cred, params, log_entry)
        else:  # oanda
            result = _execute_oanda_trade(cred, params, log_entry)

        # 10. Update log with result
        _update_log_with_result(log_entry, result, broker)

        # 10. Broadcast real-time update
        broadcast_webhook_event(user.id, log_entry)

        # 11. Return response
        return jsonify({
            'success': log_entry.status == 'success',
            'order_id': log_entry.broker_order_id,
            'webhook_log_id': log_entry.id,
            'symbol': params['symbol'],
            'action': params['action'],
            'quantity': params['quantity']
        })

    except ValueError as e:
        # Parse error - still create log entry to capture the raw payload
        logger.error(f"Parse error: {e}")

        # Create log entry even if parsing failed (for discovery/debugging)
        if not log_entry and user and raw_payload:
            try:
                log_entry = WebhookLog(
                    user_id=user.id,
                    raw_payload=raw_payload,
                    source_ip=request.remote_addr,
                    broker=broker,
                    status='parse_error',
                    error_message=f"Parse error: {str(e)}",
                    client_order_id=f"TV-{uuid.uuid4().hex[:12]}"
                )
                db.session.add(log_entry)
                db.session.commit()
                broadcast_webhook_event(user.id, log_entry)
            except Exception as db_error:
                logger.error(f"Failed to create log entry for parse error: {db_error}")
        elif log_entry:
            log_entry.status = 'parse_error'
            log_entry.error_message = f"Parse error: {str(e)}"
            db.session.commit()
            if user:
                broadcast_webhook_event(user.id, log_entry)

        return jsonify({
            'success': False,
            'error': str(e),
            'webhook_log_id': log_entry.id if log_entry else None,
            'note': 'Raw payload saved for inspection'
        }), 400

    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        if log_entry:
            log_entry.status = 'failed'
            log_entry.error_message = str(e)
            db.session.commit()
            if user:
                broadcast_webhook_event(user.id, log_entry)

        return jsonify({'success': False, 'error': 'Internal server error'}), 500


def _create_log_entry(user_id, raw_payload, broker, params, original_symbol, status='pending', error=None):
    """Create webhook log entry with TP tracking fields.
    
    Uses WebhookNormalizer for consistent parsing and stores:
    - tp_level: TP1, TP2, TP3, SL, PARTIAL, etc.
    - position_size_after: Remaining position after this action
    - entry_price: Cached entry price for P&L calculations
    
    Requirements: 1.1, 1.2, 5.1, 5.2
    """
    import json

    # Generate unique client order ID
    client_order_id = f"TV-{uuid.uuid4().hex[:12]}"

    # Serialize metadata to JSON
    metadata_json = None
    metadata = params.get('metadata', {})
    if metadata:
        try:
            metadata_json = json.dumps(metadata)
        except (TypeError, ValueError):
            logger.warning(f"Failed to serialize metadata to JSON: {metadata}")

    # Build raw payload dict for normalization
    raw_payload_dict = {}
    try:
        raw_payload_dict = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
    except (json.JSONDecodeError, TypeError):
        raw_payload_dict = {}
    
    # Normalize the webhook payload to extract TP tracking fields
    normalized = WebhookNormalizer.normalize(raw_payload_dict)
    
    # Determine trade group and direction using normalized data
    result = TradeGroupingService.determine_trade_group_from_normalized(
        user_id=user_id,
        normalized=normalized
    )
    trade_group_id = result.trade_group_id
    trade_direction = result.trade_direction
    
    # Extract TP tracking fields from normalized webhook
    tp_level = normalized.alert_type if normalized.alert_type != 'UNKNOWN' else None
    position_size_after = normalized.position_size
    
    # Determine entry_price:
    # - For entries: use the order_price from this webhook
    # - For exits: use the cached entry_price from the trade group result
    entry_price = None
    if result.is_new_group:
        # This is an entry - use the order price as entry price
        entry_price = normalized.order_price
    else:
        # This is an exit - use the cached entry price from the group
        entry_price = result.entry_price
    
    # Calculate P&L for exits (TP1, TP2, TP3, SL, PARTIAL, EXIT)
    # Requirements: 2.1, 2.2, 2.3
    realized_pnl_percent = None
    realized_pnl_absolute = None
    
    exit_alert_types = [AlertType.TP1.value, AlertType.TP2.value, AlertType.TP3.value,
                        AlertType.STOP_LOSS.value, AlertType.PARTIAL.value, AlertType.EXIT.value]
    
    if tp_level in exit_alert_types and entry_price and normalized.order_price and trade_direction:
        try:
            exit_quantity = normalized.order_contracts or params.get('quantity', 0)
            if exit_quantity and exit_quantity > 0:
                pnl_result = PnLCalculator.calculate_exit_pnl(
                    entry_price=entry_price,
                    exit_price=normalized.order_price,
                    direction=trade_direction,
                    quantity=exit_quantity
                )
                realized_pnl_percent = pnl_result.pnl_percent
                realized_pnl_absolute = pnl_result.pnl_absolute
                logger.info(f"Calculated P&L for {tp_level}: {realized_pnl_percent:.2f}% (${realized_pnl_absolute:.2f})")
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to calculate P&L: {e}")
    
    # Get leverage from normalized webhook (may be in alert_message)
    leverage = normalized.leverage or params.get('leverage')
    
    # Get stop_loss from normalized webhook (may be in alert_message)
    stop_loss = normalized.stop_loss_price or params.get('stop_loss')

    log = WebhookLog(
        user_id=user_id,
        raw_payload=raw_payload if isinstance(raw_payload, str) else json.dumps(raw_payload),
        source_ip=request.remote_addr,
        broker=broker,
        symbol=params['symbol'],
        original_symbol=original_symbol,
        action=params['action'],
        order_type=params['order_type'],
        quantity=params['quantity'],
        price=params.get('price'),
        stop_loss=stop_loss,
        take_profit=params.get('take_profit'),
        trailing_stop_pct=params.get('trailing_stop_pct'),
        leverage=leverage,
        trade_group_id=trade_group_id,
        trade_direction=trade_direction,
        # TP tracking fields
        tp_level=tp_level,
        position_size_after=position_size_after,
        entry_price=entry_price,
        # P&L fields (calculated for exits)
        realized_pnl_percent=realized_pnl_percent,
        realized_pnl_absolute=realized_pnl_absolute,
        metadata_json=metadata_json,
        status=status,
        client_order_id=client_order_id,
        error_message=error
    )
    db.session.add(log)
    db.session.commit()
    return log


def _execute_blofin_trade(cred, params, log_entry):
    """
    Execute Blofin trade using user credentials.

    Args:
        cred: UserCredentials model instance
        params: Parsed trade parameters
        log_entry: WebhookLog model instance

    Returns:
        Blofin API response dict
    """
    # Decrypt credentials
    api_key = encryption_service.decrypt(cred.api_key_encrypted)
    secret_key = encryption_service.decrypt(cred.secret_key_encrypted)
    passphrase = encryption_service.decrypt(cred.passphrase_encrypted)

    # Create client with user credentials
    client = BlofinClient(api_key, secret_key, passphrase)

    # Place order based on type
    if params['order_type'] == 'market':
        result = client.place_market_order(
            symbol=params['symbol'],
            side=params['action'],
            size=params['quantity'],
            client_order_id=log_entry.client_order_id,
            stop_loss=params.get('stop_loss'),
            take_profit=params.get('take_profit'),
            leverage=params.get('leverage')
        )
    elif params['order_type'] == 'limit':
        if not params.get('price'):
            raise ValueError("Limit order requires price")
        result = client.place_limit_order(
            symbol=params['symbol'],
            side=params['action'],
            size=params['quantity'],
            price=params['price'],
            client_order_id=log_entry.client_order_id,
            stop_loss=params.get('stop_loss'),
            take_profit=params.get('take_profit'),
            leverage=params.get('leverage')
        )
    else:
        raise ValueError(f"Unsupported order type: {params['order_type']}")

    return result


def _execute_oanda_trade(cred, params, log_entry):
    """
    Execute Oanda trade using user credentials.

    Args:
        cred: UserCredentials model instance
        params: Parsed trade parameters
        log_entry: WebhookLog model instance

    Returns:
        Oanda API response dict
    """
    # Decrypt credentials
    api_key = encryption_service.decrypt(cred.api_key_encrypted)
    account_id = encryption_service.decrypt(cred.account_id_encrypted)

    # Create client
    client = OandaClient(api_key, account_id, is_live=False)

    # Convert to signed units (positive = buy, negative = sell)
    units = int(params['quantity'])
    if params['action'] == 'sell':
        units = -units

    # Client extensions for tracking
    client_extensions = {
        "id": log_entry.client_order_id,
        "tag": "TradingView"
    }

    # Place order based on type
    if params['order_type'] == 'market':
        result = client.place_market_order(
            instrument=params['symbol'],
            units=units,
            stop_loss=params.get('stop_loss'),
            take_profit=params.get('take_profit'),
            client_extensions=client_extensions
        )
    elif params['order_type'] == 'limit':
        if not params.get('price'):
            raise ValueError("Limit order requires price")
        result = client.place_limit_order(
            instrument=params['symbol'],
            units=units,
            price=params['price'],
            stop_loss=params.get('stop_loss'),
            take_profit=params.get('take_profit'),
            client_extensions=client_extensions
        )
    elif params['order_type'] == 'stop':
        if not params.get('price'):
            raise ValueError("Stop order requires price")
        result = client.place_stop_order(
            instrument=params['symbol'],
            units=units,
            price=params['price'],
            stop_loss=params.get('stop_loss'),
            take_profit=params.get('take_profit'),
            client_extensions=client_extensions
        )
    else:
        raise ValueError(f"Unsupported order type: {params['order_type']}")

    return result


def _update_log_with_result(log_entry, result, broker):
    """
    Update log entry with broker response.

    Args:
        log_entry: WebhookLog model instance
        result: Broker API response dict
        broker: 'blofin' or 'oanda'
    """
    if broker == 'blofin':
        # Blofin returns: {"code": "0", "msg": "", "data": [{"ordId": "..."}]}
        if result.get('code') == '0':
            log_entry.status = 'success'
            # Extract order ID from response
            data = result.get('data', [])
            if data and len(data) > 0:
                log_entry.broker_order_id = data[0].get('ordId')
            logger.info(f"Blofin order successful: {log_entry.broker_order_id}")
        else:
            log_entry.status = 'failed'
            log_entry.error_message = result.get('msg', 'Unknown error')
            logger.error(f"Blofin order failed: {log_entry.error_message}")

    elif broker == 'oanda':
        # Oanda returns different fields based on order type and result
        if 'orderFillTransaction' in result:
            # Market order filled immediately
            log_entry.status = 'success'
            log_entry.broker_order_id = result['orderFillTransaction'].get('id')
            logger.info(f"Oanda order filled: {log_entry.broker_order_id}")
        elif 'orderCreateTransaction' in result:
            # Limit/stop order created (pending)
            log_entry.status = 'success'
            log_entry.broker_order_id = result['orderCreateTransaction'].get('id')
            logger.info(f"Oanda order created: {log_entry.broker_order_id}")
        elif 'error' in result:
            log_entry.status = 'failed'
            log_entry.error_message = result.get('error', 'Unknown error')
            logger.error(f"Oanda order failed: {log_entry.error_message}")
        else:
            log_entry.status = 'failed'
            log_entry.error_message = 'Unknown response format'
            logger.error(f"Oanda unknown response: {result}")

    db.session.commit()
