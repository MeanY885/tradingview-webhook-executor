"""Trade grouping service for automatically grouping related webhook entries."""
import json
import uuid
from datetime import datetime, timedelta
from app.models.webhook_log import WebhookLog
from app.extensions import db
import logging

logger = logging.getLogger(__name__)


class TradeGroupingService:
    """Service for auto-grouping related trades."""

    @staticmethod
    def determine_trade_group(user_id: int, symbol: str, params: dict, metadata: dict) -> tuple:
        """
        Determine the trade group ID and direction for a webhook.

        Args:
            user_id: User ID
            symbol: Trading symbol
            params: Parsed trade parameters
            metadata: TradingView metadata

        Returns:
            tuple: (trade_group_id, trade_direction) or (None, None)
        """
        # Extract order_type from alert_message_params if available
        alert_message_params = metadata.get('alert_message_params', {})
        order_type_from_message = alert_message_params.get('order_type', '').lower()

        # Determine trade direction from order_type
        trade_direction = None
        is_entry = False
        is_exit = False

        if 'enter_long' in order_type_from_message or 'entry_long' in order_type_from_message:
            trade_direction = 'long'
            is_entry = True
        elif 'enter_short' in order_type_from_message or 'entry_short' in order_type_from_message:
            trade_direction = 'short'
            is_entry = True
        elif 'reduce_long' in order_type_from_message or 'exit_long' in order_type_from_message:
            trade_direction = 'long'
            is_exit = True
        elif 'reduce_short' in order_type_from_message or 'exit_short' in order_type_from_message:
            trade_direction = 'short'
            is_exit = True
        else:
            # Fallback: try to infer from action and market_position
            action = params.get('action', '').lower()
            market_position = metadata.get('market_position', '').lower()

            if action == 'buy' and market_position in ['', 'flat', '0']:
                trade_direction = 'long'
                is_entry = True
            elif action == 'sell' and market_position in ['', 'flat', '0']:
                trade_direction = 'short'
                is_entry = True
            elif market_position == 'long':
                trade_direction = 'long'
                is_exit = action == 'sell'
            elif market_position == 'short':
                trade_direction = 'short'
                is_exit = action == 'buy'

        if not trade_direction:
            logger.warning(f"Could not determine trade direction for {symbol}")
            return None, None

        # If this is an entry, create a new trade group
        if is_entry:
            trade_group_id = TradeGroupingService._generate_trade_group_id(user_id, symbol, trade_direction)
            logger.info(f"New trade group created: {trade_group_id} ({trade_direction})")
            return trade_group_id, trade_direction

        # If this is an exit/reduce, find existing trade group
        if is_exit or params.get('action') in ['buy', 'sell']:
            trade_group_id = TradeGroupingService._find_active_trade_group(
                user_id, symbol, trade_direction
            )
            if trade_group_id:
                logger.info(f"Continuing trade group: {trade_group_id} ({trade_direction})")
                return trade_group_id, trade_direction
            else:
                # No active group found - this might be an orphaned exit
                # Create a new group anyway for tracking
                trade_group_id = TradeGroupingService._generate_trade_group_id(user_id, symbol, trade_direction)
                logger.warning(f"No active trade group found for {symbol} {trade_direction}, creating orphaned group: {trade_group_id}")
                return trade_group_id, trade_direction

        return None, None

    @staticmethod
    def _generate_trade_group_id(user_id: int, symbol: str, direction: str) -> str:
        """Generate a unique trade group ID."""
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        unique_id = uuid.uuid4().hex[:8].upper()
        return f"{symbol}-{direction.upper()}-{timestamp}-{unique_id}"

    @staticmethod
    def _find_active_trade_group(user_id: int, symbol: str, direction: str) -> str:
        """
        Find the most recent active trade group for a symbol and direction.

        A trade group is considered active if:
        - Same symbol and direction
        - Most recent entry within 7 days
        - Not yet closed (no flat market_position)
        """
        # Look for recent webhook logs with the same symbol and direction
        cutoff_date = datetime.utcnow() - timedelta(days=7)

        # Find the most recent trade group that's still open
        recent_logs = WebhookLog.query.filter(
            WebhookLog.user_id == user_id,
            WebhookLog.symbol == symbol,
            WebhookLog.trade_direction == direction,
            WebhookLog.trade_group_id.isnot(None),
            WebhookLog.timestamp >= cutoff_date
        ).order_by(WebhookLog.timestamp.desc()).limit(50).all()

        # Group by trade_group_id and check if still open
        groups_checked = set()
        for log in recent_logs:
            if log.trade_group_id in groups_checked:
                continue
            groups_checked.add(log.trade_group_id)

            # Check if this group is still open by looking at the latest entry
            latest_in_group = WebhookLog.query.filter_by(
                trade_group_id=log.trade_group_id
            ).order_by(WebhookLog.timestamp.desc()).first()

            if latest_in_group:
                # Check if the latest entry has closed the position
                metadata = {}
                if latest_in_group.metadata_json:
                    try:
                        metadata = json.loads(latest_in_group.metadata_json)
                    except (json.JSONDecodeError, TypeError):
                        pass

                market_position = metadata.get('market_position', '').lower()
                position_size = metadata.get('position_size', '')

                # Check if position is still open
                is_position_open = False

                # Check market_position
                if market_position and market_position not in ['flat', '0', '']:
                    is_position_open = True

                # Check position_size (handle both string and numeric)
                if position_size:
                    try:
                        size_float = float(str(position_size))
                        if size_float != 0:
                            is_position_open = True
                    except (ValueError, TypeError):
                        pass

                if is_position_open:
                    logger.info(f"Found active trade group: {log.trade_group_id} (position: {market_position}, size: {position_size})")
                    return log.trade_group_id
                else:
                    logger.debug(f"Trade group {log.trade_group_id} is closed (position: {market_position}, size: {position_size})")

        return None
