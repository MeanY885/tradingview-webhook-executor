"""WebSocket service for real-time webhook event broadcasting."""
from flask import request
from flask_socketio import emit, join_room, leave_room
from flask_jwt_extended import decode_token
from app.extensions import socketio
import logging

logger = logging.getLogger(__name__)

# Track connected users
connected_users = {}


def register_events(socketio_instance):
    """Register SocketIO event handlers."""

    @socketio_instance.on('connect')
    def handle_connect(auth):
        """Handle client connection with JWT auth."""
        try:
            # Expect auth token in connection data
            token = auth.get('token') if auth else None
            if not token:
                logger.warning(f"Connection rejected: No token provided from {request.sid}")
                return False  # Reject connection

            # Decode JWT to get user ID
            decoded = decode_token(token)
            user_id = decoded['sub']

            # Join user to their personal room
            join_room(f'user_{user_id}')
            connected_users[request.sid] = user_id

            emit('connection_status', {'status': 'connected', 'user_id': user_id})
            logger.info(f"User {user_id} connected (session: {request.sid})")

        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False

    @socketio_instance.on('disconnect')
    def handle_disconnect():
        """Handle client disconnect."""
        user_id = connected_users.pop(request.sid, None)
        if user_id:
            leave_room(f'user_{user_id}')
            logger.info(f"User {user_id} disconnected (session: {request.sid})")

    @socketio_instance.on('ping')
    def handle_ping():
        """Handle ping from client (keepalive)."""
        emit('pong', {'timestamp': request.sid})


def broadcast_webhook_event(user_id, webhook_log):
    """
    Broadcast new webhook event to user's connected clients.

    Args:
        user_id: User ID to broadcast to
        webhook_log: WebhookLog model instance
    """
    try:
        socketio.emit(
            'webhook_received',
            {
                'id': webhook_log.id,
                'timestamp': webhook_log.timestamp.isoformat(),
                'broker': webhook_log.broker,
                'symbol': webhook_log.symbol,
                'original_symbol': webhook_log.original_symbol,
                'action': webhook_log.action,
                'order_type': webhook_log.order_type,
                'quantity': webhook_log.quantity,
                'price': webhook_log.price,
                'stop_loss': webhook_log.stop_loss,
                'take_profit': webhook_log.take_profit,
                'status': webhook_log.status,
                'broker_order_id': webhook_log.broker_order_id,
                'client_order_id': webhook_log.client_order_id,
                'error_message': webhook_log.error_message
            },
            room=f'user_{user_id}'
        )
        logger.info(f"Broadcasted webhook event {webhook_log.id} to user {user_id}")
    except Exception as e:
        logger.error(f"Failed to broadcast webhook event: {e}")


def broadcast_order_update(user_id, order_data):
    """
    Broadcast order update to user's connected clients.

    Args:
        user_id: User ID to broadcast to
        order_data: Order update data as dict
    """
    try:
        socketio.emit(
            'order_update',
            order_data,
            room=f'user_{user_id}'
        )
        logger.info(f"Broadcasted order update to user {user_id}")
    except Exception as e:
        logger.error(f"Failed to broadcast order update: {e}")
