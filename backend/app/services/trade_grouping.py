"""Trade grouping service for automatically grouping related webhook entries.

This module provides trade grouping functionality using the WebhookNormalizer
for robust parsing of TradingView webhook data.

Requirements: 1.3, 1.4, 4.1, 4.2
"""
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Tuple
from app.models.webhook_log import WebhookLog
from app.extensions import db
from app.services.webhook_normalizer import WebhookNormalizer, NormalizedWebhook, AlertType
import logging

logger = logging.getLogger(__name__)


@dataclass
class TradeGroupResult:
    """Result of trade group determination.
    
    Attributes:
        trade_group_id: Unique identifier for the trade group
        trade_direction: 'long' or 'short'
        is_new_group: True if a new group was created
        entry_price: Cached entry price (from entry or looked up)
    """
    trade_group_id: Optional[str]
    trade_direction: Optional[str]
    is_new_group: bool = False
    entry_price: Optional[float] = None


class TradeGroupingService:
    """Service for auto-grouping related trades.
    
    Uses WebhookNormalizer for consistent data parsing and provides
    trade group management based on position state.
    
    Requirements: 1.3, 1.4, 4.1, 4.2
    """

    @staticmethod
    def determine_trade_group_from_normalized(user_id: int, normalized: NormalizedWebhook) -> TradeGroupResult:
        """
        Determine trade group using normalized webhook data.
        
        This is the preferred method that uses WebhookNormalizer for consistent parsing.
        
        Args:
            user_id: User ID
            normalized: NormalizedWebhook instance from WebhookNormalizer.normalize()
            
        Returns:
            TradeGroupResult with trade_group_id, trade_direction, is_new_group, entry_price
            
        Requirements: 1.3, 1.4, 4.1, 4.2
        """
        symbol = normalized.symbol
        order_type = normalized.order_type or ''
        alert_type = normalized.alert_type
        action = normalized.action
        market_position = normalized.market_position
        is_position_closed = normalized.is_position_closed
        
        # Determine trade direction from order_type
        trade_direction = None
        is_entry = False
        is_exit = False
        
        # Check order_type for direction
        if 'long' in order_type:
            trade_direction = 'long'
        elif 'short' in order_type:
            trade_direction = 'short'
        
        # Check if entry or exit based on alert_type
        if alert_type == AlertType.ENTRY.value:
            is_entry = True
        elif alert_type in [AlertType.TP1.value, AlertType.TP2.value, AlertType.TP3.value,
                           AlertType.STOP_LOSS.value, AlertType.PARTIAL.value, AlertType.EXIT.value]:
            is_exit = True
        
        # Fallback: infer from order_type keywords
        if not is_entry and not is_exit:
            if 'enter_' in order_type or 'entry_' in order_type:
                is_entry = True
            elif 'reduce_' in order_type or 'exit_' in order_type:
                is_exit = True
        
        # Fallback: infer direction from market_position if not determined
        if not trade_direction:
            if market_position == 'long':
                trade_direction = 'long'
            elif market_position == 'short':
                trade_direction = 'short'
            elif action == 'buy' and market_position in ['', 'flat']:
                trade_direction = 'long'
                is_entry = True
            elif action == 'sell' and market_position in ['', 'flat']:
                trade_direction = 'short'
                is_entry = True
        
        if not trade_direction:
            logger.warning(f"Could not determine trade direction for {symbol}")
            return TradeGroupResult(trade_group_id=None, trade_direction=None)
        
        # If this is an entry, create a new trade group
        if is_entry:
            trade_group_id = TradeGroupingService._generate_trade_group_id(user_id, symbol, trade_direction)
            logger.info(f"New trade group created: {trade_group_id} ({trade_direction})")
            return TradeGroupResult(
                trade_group_id=trade_group_id,
                trade_direction=trade_direction,
                is_new_group=True,
                entry_price=normalized.order_price  # Entry price from the entry webhook
            )
        
        # If this is an exit/reduce, find existing trade group
        if is_exit:
            # Use position_size and timestamp as hints for matching concurrent trades
            # For reduce alerts, the position_size in the webhook is the REMAINING size after the action
            # We need to find a group whose current position matches what we expect
            position_size_hint = normalized.position_size
            timestamp_hint = normalized.timestamp
            
            trade_group_id = TradeGroupingService._find_active_trade_group(
                user_id, symbol, trade_direction,
                position_size_hint=position_size_hint,
                timestamp_hint=timestamp_hint
            )
            entry_price = None
            
            if trade_group_id:
                # Look up entry price from the group's entry webhook
                entry_price = TradeGroupingService._get_group_entry_price(trade_group_id)
                logger.info(f"Continuing trade group: {trade_group_id} ({trade_direction})")
            else:
                # No active group found - this might be an orphaned exit
                # Create a new group anyway for tracking
                trade_group_id = TradeGroupingService._generate_trade_group_id(user_id, symbol, trade_direction)
                logger.warning(f"No active trade group found for {symbol} {trade_direction}, creating orphaned group: {trade_group_id}")
            
            return TradeGroupResult(
                trade_group_id=trade_group_id,
                trade_direction=trade_direction,
                is_new_group=False,
                entry_price=entry_price
            )
        
        return TradeGroupResult(trade_group_id=None, trade_direction=None)

    @staticmethod
    def determine_trade_group(user_id: int, symbol: str, params: dict, metadata: dict) -> tuple:
        """
        Determine the trade group ID and direction for a webhook.
        
        This is the legacy method maintained for backwards compatibility.
        Internally uses WebhookNormalizer for consistent parsing.

        Args:
            user_id: User ID
            symbol: Trading symbol
            params: Parsed trade parameters
            metadata: TradingView metadata

        Returns:
            tuple: (trade_group_id, trade_direction) or (None, None)
        """
        # Build raw payload from params and metadata for normalization
        raw_payload = {
            'ticker': symbol,
            'symbol': symbol,
            'action': params.get('action', ''),
            'order_action': params.get('action', ''),
            'order_price': params.get('price'),
            'order_contracts': params.get('quantity'),
            'position_size': metadata.get('position_size'),
            'market_position': metadata.get('market_position', ''),
            'order_id': metadata.get('order_id'),
            'order_comment': metadata.get('order_comment'),
        }
        
        # Include alert_message_params as order_alert_message if present
        alert_message_params = metadata.get('alert_message_params', {})
        if alert_message_params:
            raw_payload['order_alert_message'] = json.dumps(alert_message_params)
        
        # Normalize the payload
        normalized = WebhookNormalizer.normalize(raw_payload)
        
        # Use the new method
        result = TradeGroupingService.determine_trade_group_from_normalized(user_id, normalized)
        
        return result.trade_group_id, result.trade_direction
    
    @staticmethod
    def get_trade_group_status(trade_group_id: str) -> str:
        """
        Get the status of a trade group based on the latest webhook.
        
        A group is CLOSED if the latest webhook has:
        - position_size = 0 AND market_position = 'flat'
        
        Args:
            trade_group_id: The trade group ID to check
            
        Returns:
            'ACTIVE' or 'CLOSED'
            
        Requirements: 1.3
        """
        latest = WebhookLog.query.filter_by(
            trade_group_id=trade_group_id
        ).order_by(WebhookLog.timestamp.desc()).first()
        
        if not latest:
            return 'CLOSED'  # No webhooks means closed
        
        # Check position_size_after field first (new field)
        if latest.position_size_after is not None and latest.position_size_after == 0:
            # Also check metadata for market_position
            metadata = {}
            if latest.metadata_json:
                try:
                    metadata = json.loads(latest.metadata_json)
                except (json.JSONDecodeError, TypeError):
                    pass
            
            market_position = metadata.get('market_position', '').lower()
            if market_position == 'flat':
                return 'CLOSED'
        
        # Fallback: check metadata_json for position state
        metadata = {}
        if latest.metadata_json:
            try:
                metadata = json.loads(latest.metadata_json)
            except (json.JSONDecodeError, TypeError):
                pass
        
        market_position = metadata.get('market_position', '').lower()
        position_size = metadata.get('position_size', '')
        
        # Check if position is closed
        try:
            size_float = float(str(position_size)) if position_size else None
            if size_float == 0 and market_position == 'flat':
                return 'CLOSED'
        except (ValueError, TypeError):
            pass
        
        return 'ACTIVE'
    
    @staticmethod
    def _get_group_entry_price(trade_group_id: str) -> Optional[float]:
        """
        Get the entry price for a trade group from its entry webhook.
        
        Args:
            trade_group_id: The trade group ID
            
        Returns:
            Entry price as float, or None if not found
        """
        # Find the entry webhook (first webhook in the group or one with entry_price set)
        entry_log = WebhookLog.query.filter_by(
            trade_group_id=trade_group_id
        ).order_by(WebhookLog.timestamp.asc()).first()
        
        if entry_log:
            # Check if entry_price is already cached
            if entry_log.entry_price is not None:
                return entry_log.entry_price
            # Fallback to price field
            if entry_log.price is not None:
                return entry_log.price
        
        return None

    @staticmethod
    def _generate_trade_group_id(user_id: int, symbol: str, direction: str) -> str:
        """Generate a unique trade group ID."""
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        unique_id = uuid.uuid4().hex[:8].upper()
        return f"{symbol}-{direction.upper()}-{timestamp}-{unique_id}"

    @staticmethod
    def _find_active_trade_group(
        user_id: int, 
        symbol: str, 
        direction: str,
        position_size_hint: Optional[float] = None,
        timestamp_hint: Optional[datetime] = None
    ) -> Optional[str]:
        """
        Find the best matching active trade group for a symbol and direction.

        A trade group is considered active if:
        - Same symbol and direction
        - Most recent entry within 7 days
        - Not yet closed (position_size > 0 OR market_position != 'flat')
        
        When multiple active groups exist (concurrent trades), uses:
        1. Position size continuity - match reduce alerts to groups with matching position size
        2. Timestamp proximity - prefer groups with most recent activity
        
        Uses is_position_closed logic from WebhookNormalizer for consistency.
        
        Args:
            user_id: User ID
            symbol: Trading symbol
            direction: Trade direction ('long' or 'short')
            position_size_hint: Expected position size before this action (for matching)
            timestamp_hint: Timestamp of the incoming webhook (for proximity matching)
        
        Returns:
            trade_group_id of the best matching active group, or None
        
        Requirements: 1.3, 1.4, 6.1, 6.2
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
        ).order_by(WebhookLog.timestamp.desc()).limit(100).all()

        # Collect all active groups with their latest state
        active_groups = []
        groups_checked = set()
        
        for log in recent_logs:
            if log.trade_group_id in groups_checked:
                continue
            groups_checked.add(log.trade_group_id)

            # Check if this group is still open using get_trade_group_status
            status = TradeGroupingService.get_trade_group_status(log.trade_group_id)
            
            if status == 'ACTIVE':
                # Get the latest position size for this group
                latest_log = WebhookLog.query.filter_by(
                    trade_group_id=log.trade_group_id
                ).order_by(WebhookLog.timestamp.desc()).first()
                
                latest_position_size = None
                latest_timestamp = None
                
                if latest_log:
                    latest_timestamp = latest_log.timestamp
                    # Try to get position size from position_size_after field
                    if latest_log.position_size_after is not None:
                        latest_position_size = latest_log.position_size_after
                    else:
                        # Fallback to metadata
                        if latest_log.metadata_json:
                            try:
                                metadata = json.loads(latest_log.metadata_json)
                                pos_size = metadata.get('position_size')
                                if pos_size is not None:
                                    latest_position_size = float(str(pos_size))
                            except (json.JSONDecodeError, TypeError, ValueError):
                                pass
                
                active_groups.append({
                    'trade_group_id': log.trade_group_id,
                    'latest_position_size': latest_position_size,
                    'latest_timestamp': latest_timestamp
                })
                logger.debug(f"Found active trade group: {log.trade_group_id}, position_size={latest_position_size}")
        
        if not active_groups:
            return None
        
        # If only one active group, return it
        if len(active_groups) == 1:
            logger.info(f"Found single active trade group: {active_groups[0]['trade_group_id']}")
            return active_groups[0]['trade_group_id']
        
        # Multiple active groups - need to find the best match
        logger.info(f"Found {len(active_groups)} active trade groups for {symbol} {direction}, using matching heuristics")
        
        # Strategy 1: Position size continuity matching
        # If we have a position_size_hint, find the group whose latest position_size matches
        if position_size_hint is not None:
            for group in active_groups:
                if group['latest_position_size'] is not None:
                    # Check if position sizes match (with small tolerance for floating point)
                    if abs(group['latest_position_size'] - position_size_hint) < 0.0001:
                        logger.info(f"Matched trade group by position size continuity: {group['trade_group_id']}")
                        return group['trade_group_id']
        
        # Strategy 2: Timestamp proximity matching
        # Find the group with the most recent activity (closest to the incoming webhook)
        if timestamp_hint is not None:
            best_group = None
            smallest_delta = None
            
            for group in active_groups:
                if group['latest_timestamp'] is not None:
                    delta = abs((timestamp_hint - group['latest_timestamp']).total_seconds())
                    if smallest_delta is None or delta < smallest_delta:
                        smallest_delta = delta
                        best_group = group
            
            if best_group:
                logger.info(f"Matched trade group by timestamp proximity: {best_group['trade_group_id']} (delta={smallest_delta}s)")
                return best_group['trade_group_id']
        
        # Fallback: Return the most recently active group
        # Sort by latest_timestamp descending
        active_groups.sort(
            key=lambda g: g['latest_timestamp'] if g['latest_timestamp'] else datetime.min,
            reverse=True
        )
        
        logger.info(f"Fallback to most recent active trade group: {active_groups[0]['trade_group_id']}")
        return active_groups[0]['trade_group_id']
    
    @staticmethod
    def _find_all_active_trade_groups(user_id: int, symbol: str, direction: str) -> list:
        """
        Find all active trade groups for a symbol and direction.
        
        Used to detect concurrent trades on the same symbol.
        
        Args:
            user_id: User ID
            symbol: Trading symbol
            direction: Trade direction ('long' or 'short')
        
        Returns:
            List of trade_group_ids that are currently active
        
        Requirements: 6.1, 6.3
        """
        cutoff_date = datetime.utcnow() - timedelta(days=7)

        recent_logs = WebhookLog.query.filter(
            WebhookLog.user_id == user_id,
            WebhookLog.symbol == symbol,
            WebhookLog.trade_direction == direction,
            WebhookLog.trade_group_id.isnot(None),
            WebhookLog.timestamp >= cutoff_date
        ).order_by(WebhookLog.timestamp.desc()).limit(100).all()

        active_groups = []
        groups_checked = set()
        
        for log in recent_logs:
            if log.trade_group_id in groups_checked:
                continue
            groups_checked.add(log.trade_group_id)

            status = TradeGroupingService.get_trade_group_status(log.trade_group_id)
            
            if status == 'ACTIVE':
                active_groups.append(log.trade_group_id)
        
        return active_groups
