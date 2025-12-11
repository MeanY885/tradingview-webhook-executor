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
from app.models.symbol_config import SymbolConfig
from app.extensions import db
from app.services.webhook_normalizer import WebhookNormalizer, NormalizedWebhook, AlertType
import logging

logger = logging.getLogger(__name__)


def determine_trade_group_for_oanda_signal(
    user_id: int,
    symbol: str,
    direction: str,
    is_entry: bool,
    closes_position: bool,
    entry_price: Optional[float] = None
) -> 'TradeGroupResult':
    """
    Determine trade group for Oanda indicator signals.
    
    SIMPLE RULE FOR OANDA FOREX:
    - Entry (bull_entry/bear_entry) → Create new trade group
    - Any other signal → Find the active trade for this symbol
    - TP1 or SL → Closes the trade (handled by closes_position flag)
    
    One active trade per symbol at a time.
    
    Args:
        user_id: User ID
        symbol: Trading symbol (e.g., 'EURUSD')
        direction: Trade direction ('long' or 'short')
        is_entry: True if this is an entry signal
        closes_position: True if this signal closes the trade (TP1/SL for tp_count=1)
        entry_price: Entry price for entries
        
    Returns:
        TradeGroupResult with trade_group_id, trade_direction, is_new_group, entry_price
    """
    if is_entry:
        # Entry signal - always create a new trade group
        trade_group_id = TradeGroupingService._generate_trade_group_id(user_id, symbol, direction)
        logger.info(f"[Oanda] New trade group created: {trade_group_id} ({direction})")
        return TradeGroupResult(
            trade_group_id=trade_group_id,
            trade_direction=direction,
            is_new_group=True,
            entry_price=entry_price
        )
    
    # Non-entry signal - find the active trade for this symbol
    # Try both directions since we want ANY active trade for this symbol
    trade_group_id = None
    found_direction = direction
    
    for try_direction in [direction, 'short' if direction == 'long' else 'long']:
        trade_group_id = TradeGroupingService._find_active_trade_group_for_oanda(
            user_id, symbol, try_direction
        )
        if trade_group_id:
            found_direction = try_direction
            break
    
    if trade_group_id:
        # Found active trade - get entry price from the group
        group_entry_price = TradeGroupingService._get_group_entry_price(trade_group_id)
        logger.info(f"[Oanda] Continuing trade group: {trade_group_id} ({found_direction}) closes_position={closes_position}")
        return TradeGroupResult(
            trade_group_id=trade_group_id,
            trade_direction=found_direction,
            is_new_group=False,
            entry_price=group_entry_price
        )
    else:
        # No active group found - create orphaned group for tracking
        trade_group_id = TradeGroupingService._generate_trade_group_id(user_id, symbol, direction)
        logger.warning(f"[Oanda] No active trade group found for {symbol}, creating orphaned group: {trade_group_id}")
        return TradeGroupResult(
            trade_group_id=trade_group_id,
            trade_direction=direction,
            is_new_group=False,
            entry_price=None
        )


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
                           AlertType.TP4.value, AlertType.TP5.value,
                           AlertType.STOP_LOSS.value, AlertType.PARTIAL.value, AlertType.EXIT.value]:
            is_exit = True
        
        # Fallback: infer from order_type keywords
        if not is_entry and not is_exit:
            if 'enter_' in order_type or 'entry_' in order_type:
                is_entry = True
            elif 'reduce_' in order_type or 'exit_' in order_type:
                is_exit = True
        
        # IMPORTANT: Use prev_market_position to detect entry/exit for single-condition indicators
        # This handles cases where order_type doesn't change but position state does
        prev_market_position = normalized.prev_market_position
        
        if prev_market_position and not is_entry and not is_exit:
            # Entry: flat → long/short
            if prev_market_position == 'flat' and market_position in ['long', 'short']:
                is_entry = True
                trade_direction = market_position
                logger.info(f"Detected entry via prev_market_position: flat → {market_position}")
            # Exit: long/short → flat
            elif prev_market_position in ['long', 'short'] and market_position == 'flat':
                is_exit = True
                trade_direction = prev_market_position  # Direction of the closed position
                logger.info(f"Detected exit via prev_market_position: {prev_market_position} → flat")
            # Reversal: long → short or short → long
            elif prev_market_position == 'long' and market_position == 'short':
                # This is both an exit (close long) and entry (open short)
                # For grouping purposes, treat as exit of the previous position
                is_exit = True
                trade_direction = 'long'  # Closing the long
                logger.info(f"Detected reversal: long → short (treating as exit long)")
            elif prev_market_position == 'short' and market_position == 'long':
                is_exit = True
                trade_direction = 'short'  # Closing the short
                logger.info(f"Detected reversal: short → long (treating as exit short)")
        
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

            trade_group_id = None
            entry_price = None

            # If direction is known, try to find by direction
            if trade_direction:
                trade_group_id = TradeGroupingService._find_active_trade_group(
                    user_id, symbol, trade_direction,
                    position_size_hint=position_size_hint,
                    timestamp_hint=timestamp_hint
                )

            # If direction unknown or no group found, try to find ANY active group for this symbol
            # This handles the case where only one position is open per symbol at a time
            if not trade_group_id:
                for direction in ['long', 'short']:
                    trade_group_id = TradeGroupingService._find_active_trade_group(
                        user_id, symbol, direction,
                        position_size_hint=position_size_hint,
                        timestamp_hint=timestamp_hint
                    )
                    if trade_group_id:
                        trade_direction = direction  # Inherit direction from found group
                        logger.info(f"Found active {direction} group for {symbol} exit signal")
                        break

            if trade_group_id:
                # Look up entry price from the group's entry webhook
                entry_price = TradeGroupingService._get_group_entry_price(trade_group_id)
                logger.info(f"Continuing trade group: {trade_group_id} ({trade_direction})")
            else:
                # No active group found - this might be an orphaned exit
                # Create a new group anyway for tracking
                if not trade_direction:
                    trade_direction = 'long'  # Default fallback
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
        Get the status of a trade group based on webhooks.
        
        A group is CLOSED if ANY of these conditions are met:
        1. position_size = 0 in any webhook (actual position closed)
        2. EXIT signal received
        3. Final TP hit (based on tp_count from SymbolConfig)
        4. Final SL hit (based on sl_count from SymbolConfig)
        5. metadata.closes_position = True
        
        IMPORTANT: position_size = 0 takes priority over TP/SL config.
        
        Args:
            trade_group_id: The trade group ID to check
            
        Returns:
            'ACTIVE' or 'CLOSED'
            
        Requirements: 1.3
        """
        # Get all webhooks in the group, ordered by timestamp
        webhooks = WebhookLog.query.filter_by(
            trade_group_id=trade_group_id
        ).order_by(WebhookLog.timestamp.asc()).all()
        
        if not webhooks:
            return 'CLOSED'  # No webhooks means closed
        
        entry_webhook = webhooks[0]
        
        # Get tp_count and sl_count from SymbolConfig
        symbol_config = SymbolConfig.get_config(
            user_id=entry_webhook.user_id,
            symbol=entry_webhook.symbol,
            broker=entry_webhook.broker or 'oanda'
        )
        tp_count = symbol_config.tp_count
        sl_count = symbol_config.sl_count
        
        # Determine which TP/SL level closes the trade
        closing_tp = f'TP{tp_count}'
        closing_sl = f'SL{sl_count}' if sl_count > 1 else 'SL'
        
        for webhook in webhooks:
            # PRIORITY 1: Check actual position size
            # If position_size = 0, trade is closed regardless of TP/SL config
            if webhook.position_size_after is not None and webhook.position_size_after == 0:
                return 'CLOSED'
            
            # Check metadata for position_size and closes_position
            if webhook.metadata_json:
                try:
                    metadata = json.loads(webhook.metadata_json)
                    
                    # Check position_size in metadata
                    pos_size = metadata.get('position_size')
                    if pos_size is not None:
                        try:
                            if float(str(pos_size)) == 0:
                                return 'CLOSED'
                        except (ValueError, TypeError):
                            pass
                    
                    # Check closes_position flag
                    if metadata.get('closes_position') is True:
                        return 'CLOSED'
                except (json.JSONDecodeError, TypeError):
                    pass
            
            # PRIORITY 2: Check signal type (tp_level)
            if webhook.tp_level:
                tp_level = webhook.tp_level.upper()
                
                # EXIT always closes
                if tp_level == 'EXIT':
                    return 'CLOSED'
                
                # Check for final SL
                if sl_count == 1 and tp_level in ['SL', 'SL1']:
                    return 'CLOSED'
                if sl_count > 1 and tp_level == closing_sl:
                    return 'CLOSED'
                
                # Check for final TP
                if tp_level == closing_tp:
                    return 'CLOSED'
        
        # Check latest webhook for position state (fallback for non-Oanda trades)
        latest = webhooks[-1]  # Most recent
        
        # Check position_size_after field
        if latest.position_size_after is not None and latest.position_size_after == 0:
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
    def _find_active_trade_group_for_oanda(
        user_id: int,
        symbol: str,
        direction: str
    ) -> Optional[str]:
        """
        Find the active trade group for an Oanda forex symbol.
        
        SIMPLE RULE: A trade is active until TP1 or SL is hit.
        Only one active trade per symbol at a time.
        
        A trade group is CLOSED if any webhook in the group has:
        - tp_level = 'TP1' or 'SL' (for tp_count=1 trades)
        - metadata.closes_position = True
        
        Args:
            user_id: User ID
            symbol: Trading symbol (e.g., 'EUR_USD')
            direction: Trade direction ('long' or 'short')
            
        Returns:
            trade_group_id of the active group, or None if no active trade
        """
        cutoff_date = datetime.utcnow() - timedelta(days=7)
        
        # Find all recent trade groups for this symbol
        recent_logs = WebhookLog.query.filter(
            WebhookLog.user_id == user_id,
            WebhookLog.symbol == symbol,
            WebhookLog.trade_direction == direction,
            WebhookLog.trade_group_id.isnot(None),
            WebhookLog.timestamp >= cutoff_date
        ).order_by(WebhookLog.timestamp.desc()).limit(50).all()
        
        # Check each group to see if it's still active
        groups_checked = set()
        
        for log in recent_logs:
            if log.trade_group_id in groups_checked:
                continue
            groups_checked.add(log.trade_group_id)
            
            # Check if this group has been closed (TP1 or SL hit)
            if TradeGroupingService._is_oanda_trade_closed(log.trade_group_id):
                continue
            
            # Found an active group
            logger.info(f"[Oanda] Found active trade group: {log.trade_group_id}")
            return log.trade_group_id
        
        return None
    
    @staticmethod
    def _is_oanda_trade_closed(trade_group_id: str) -> bool:
        """
        Check if an Oanda trade group is closed.
        
        A trade is closed if ANY of these conditions are met:
        1. position_size = 0 in the latest webhook (actual position closed)
        2. EXIT signal received
        3. Final TP hit (based on tp_count from SymbolConfig)
        4. Final SL hit (based on sl_count from SymbolConfig)
        5. metadata.closes_position = True
        
        IMPORTANT: position_size = 0 takes priority over TP/SL config.
        If the indicator closes 100% on TP1, the trade is closed even if
        tp_count = 3 in the config.
        
        Args:
            trade_group_id: The trade group ID to check
            
        Returns:
            True if the trade is closed, False if still active
        """
        # Get all webhooks in this group, ordered by timestamp
        webhooks = WebhookLog.query.filter_by(
            trade_group_id=trade_group_id
        ).order_by(WebhookLog.timestamp.asc()).all()
        
        if not webhooks:
            return True  # No webhooks = closed
        
        entry_webhook = webhooks[0]
        
        # Get tp_count and sl_count from SymbolConfig
        symbol_config = SymbolConfig.get_config(
            user_id=entry_webhook.user_id,
            symbol=entry_webhook.symbol,
            broker=entry_webhook.broker or 'oanda'
        )
        tp_count = symbol_config.tp_count
        sl_count = symbol_config.sl_count
        
        # Determine which TP/SL level closes the trade
        closing_tp = f'TP{tp_count}'  # TP1, TP2, or TP3
        closing_sl = f'SL{sl_count}' if sl_count > 1 else 'SL'  # SL, SL2, or SL3
        
        logger.debug(f"Checking trade {trade_group_id}: closing_tp={closing_tp}, closing_sl={closing_sl}")
        
        for webhook in webhooks:
            # PRIORITY 1: Check actual position size
            # If position_size = 0, trade is closed regardless of TP/SL config
            position_closed_by_size = False
            
            # Check position_size_after field first
            if webhook.position_size_after is not None and webhook.position_size_after == 0:
                position_closed_by_size = True
            
            # Also check metadata for position_size
            if webhook.metadata_json:
                try:
                    metadata = json.loads(webhook.metadata_json)
                    pos_size = metadata.get('position_size')
                    if pos_size is not None:
                        try:
                            if float(str(pos_size)) == 0:
                                position_closed_by_size = True
                        except (ValueError, TypeError):
                            pass
                    
                    # Check closes_position flag
                    if metadata.get('closes_position') is True:
                        logger.debug(f"Trade group {trade_group_id} closed by closes_position flag")
                        return True
                except (json.JSONDecodeError, TypeError):
                    pass
            
            if position_closed_by_size:
                logger.debug(f"Trade group {trade_group_id} closed by position_size=0")
                return True
            
            # PRIORITY 2: Check signal type
            if webhook.tp_level:
                tp_level = webhook.tp_level.upper()
                
                # EXIT always closes
                if tp_level == 'EXIT':
                    logger.debug(f"Trade group {trade_group_id} closed by EXIT")
                    return True
                
                # Check for SL (handle both 'SL' and 'SL1', 'SL2', 'SL3')
                # Single SL config: any SL closes
                if sl_count == 1 and tp_level in ['SL', 'SL1']:
                    logger.debug(f"Trade group {trade_group_id} closed by {tp_level}")
                    return True
                
                # Multi-SL config: only final SL closes
                if sl_count > 1 and tp_level == closing_sl:
                    logger.debug(f"Trade group {trade_group_id} closed by final SL: {tp_level}")
                    return True
                
                # Check if this is the final TP
                if tp_level == closing_tp:
                    logger.debug(f"Trade group {trade_group_id} closed by final TP: {closing_tp}")
                    return True
        
        return False

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

    @staticmethod
    def detect_sltp_changes(
        trade_group_id: str,
        current_sl: Optional[float],
        current_tp: Optional[float]
    ) -> Tuple[bool, bool]:
        """
        Detect if SL or TP values have changed from the previous webhook in the group.
        
        Compares the current SL/TP values with the most recent webhook in the group
        that has non-null SL/TP values.
        
        Args:
            trade_group_id: The trade group ID to check
            current_sl: Current stop loss value (may be None)
            current_tp: Current take profit value (may be None)
            
        Returns:
            Tuple of (sl_changed, tp_changed) boolean flags
            
        Requirements: 1.3, 1.4
        """
        sl_changed = False
        tp_changed = False
        
        # Get the previous webhook in this group with SL/TP values
        previous_log = WebhookLog.query.filter(
            WebhookLog.trade_group_id == trade_group_id
        ).order_by(WebhookLog.timestamp.desc()).first()
        
        if not previous_log:
            # No previous webhook, so no change to detect
            return sl_changed, tp_changed
        
        # Get previous SL value (check current_stop_loss first, then stop_loss)
        previous_sl = previous_log.current_stop_loss
        if previous_sl is None:
            previous_sl = previous_log.stop_loss
        
        # Get previous TP value (check current_take_profit first, then take_profit)
        previous_tp = previous_log.current_take_profit
        if previous_tp is None:
            previous_tp = previous_log.take_profit
        
        # Detect SL change
        if current_sl is not None and previous_sl is not None:
            # Both have values - check if they differ
            if abs(current_sl - previous_sl) > 0.0001:
                sl_changed = True
        elif current_sl is not None and previous_sl is None:
            # New SL value where there was none before
            sl_changed = True
        # Note: We don't flag as changed if current_sl is None (SL removed)
        
        # Detect TP change
        if current_tp is not None and previous_tp is not None:
            # Both have values - check if they differ
            if abs(current_tp - previous_tp) > 0.0001:
                tp_changed = True
        elif current_tp is not None and previous_tp is None:
            # New TP value where there was none before
            tp_changed = True
        # Note: We don't flag as changed if current_tp is None (TP removed)
        
        logger.debug(
            f"SL/TP change detection for {trade_group_id}: "
            f"prev_sl={previous_sl}, curr_sl={current_sl}, sl_changed={sl_changed}, "
            f"prev_tp={previous_tp}, curr_tp={current_tp}, tp_changed={tp_changed}"
        )
        
        return sl_changed, tp_changed

    @staticmethod
    def get_most_recent_sltp(trade_group_id: str) -> dict:
        """
        Get the most recent SL/TP values for a trade group.
        
        Queries the latest webhook in the group that has non-null SL/TP values
        and returns the current SL, TP, and trailing stop information.
        
        Args:
            trade_group_id: The trade group ID to query
            
        Returns:
            Dict with keys:
                - current_stop_loss: Most recent SL value (or None)
                - current_take_profit: Most recent TP value (or None)
                - exit_trail_price: Trailing stop price (or None)
                - exit_trail_offset: Trailing stop offset (or None)
                - timestamp: Timestamp of the webhook with these values
                
        Requirements: 1.5
        """
        result = {
            'current_stop_loss': None,
            'current_take_profit': None,
            'exit_trail_price': None,
            'exit_trail_offset': None,
            'timestamp': None
        }
        
        # Get all webhooks in the group, ordered by timestamp descending
        webhooks = WebhookLog.query.filter(
            WebhookLog.trade_group_id == trade_group_id
        ).order_by(WebhookLog.timestamp.desc()).all()
        
        if not webhooks:
            return result
        
        # Find the most recent non-null SL value
        for webhook in webhooks:
            sl_value = webhook.current_stop_loss or webhook.stop_loss
            if sl_value is not None and result['current_stop_loss'] is None:
                result['current_stop_loss'] = sl_value
                if result['timestamp'] is None:
                    result['timestamp'] = webhook.timestamp
                break
        
        # Find the most recent non-null TP value
        for webhook in webhooks:
            tp_value = webhook.current_take_profit or webhook.take_profit
            if tp_value is not None and result['current_take_profit'] is None:
                result['current_take_profit'] = tp_value
                if result['timestamp'] is None:
                    result['timestamp'] = webhook.timestamp
                break
        
        # Find the most recent trailing stop info
        for webhook in webhooks:
            if webhook.exit_trail_price is not None and result['exit_trail_price'] is None:
                result['exit_trail_price'] = webhook.exit_trail_price
            if webhook.exit_trail_offset is not None and result['exit_trail_offset'] is None:
                result['exit_trail_offset'] = webhook.exit_trail_offset
            if result['exit_trail_price'] is not None and result['exit_trail_offset'] is not None:
                break
        
        logger.debug(
            f"Most recent SL/TP for {trade_group_id}: "
            f"sl={result['current_stop_loss']}, tp={result['current_take_profit']}, "
            f"trail_price={result['exit_trail_price']}, trail_offset={result['exit_trail_offset']}"
        )
        
        return result


@dataclass
class TPHitStatus:
    """TP hit status for a trade group.
    
    **Feature: trade-enhancements, Property 10: TP Hit Detection**
    **Feature: trade-enhancements, Property 11: All TPs Complete Detection**
    **Validates: Requirements 3.2, 3.5**
    """
    tp1_hit: bool = False
    tp1_timestamp: Optional[datetime] = None
    tp1_price: Optional[float] = None
    tp1_pnl_percent: Optional[float] = None
    
    tp2_hit: bool = False
    tp2_timestamp: Optional[datetime] = None
    tp2_price: Optional[float] = None
    tp2_pnl_percent: Optional[float] = None
    
    tp3_hit: bool = False
    tp3_timestamp: Optional[datetime] = None
    tp3_price: Optional[float] = None
    tp3_pnl_percent: Optional[float] = None
    
    all_tps_complete: bool = False


def get_tp_hit_status(trades: list) -> TPHitStatus:
    """
    Extract TP hit status from a list of trade webhooks.
    
    A TP level (TP1, TP2, TP3) is marked as "hit" if and only if there exists
    a webhook in the group with tp_level equal to that TP level.
    
    **Feature: trade-enhancements, Property 10: TP Hit Detection**
    **Validates: Requirements 3.2**
    
    Args:
        trades: List of trade/webhook dictionaries or WebhookLog objects
        
    Returns:
        TPHitStatus object with hit flags and details
    """
    result = TPHitStatus()
    
    if not trades:
        return result
    
    for trade in trades:
        # Handle both dict and WebhookLog objects
        if hasattr(trade, 'tp_level'):
            tp_level = trade.tp_level
            timestamp = trade.timestamp
            price = trade.price
            pnl_percent = getattr(trade, 'realized_pnl_percent', None)
        elif isinstance(trade, dict):
            tp_level = trade.get('tp_level')
            timestamp = trade.get('timestamp')
            price = trade.get('price')
            pnl_percent = trade.get('realized_pnl_percent')
            
            # Also check metadata for tp_level detection
            if not tp_level:
                metadata = trade.get('metadata', {})
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except (json.JSONDecodeError, TypeError):
                        metadata = {}
                
                order_comment = metadata.get('order_comment', '').upper()
                order_id = metadata.get('order_id', '').lower()
                
                if 'TP1' in order_comment or '1st target' in order_id:
                    tp_level = 'TP1'
                elif 'TP2' in order_comment or '2nd target' in order_id:
                    tp_level = 'TP2'
                elif 'TP3' in order_comment or '3rd target' in order_id:
                    tp_level = 'TP3'
        else:
            continue
        
        # Mark TP as hit
        if tp_level == 'TP1' and not result.tp1_hit:
            result.tp1_hit = True
            result.tp1_timestamp = timestamp
            result.tp1_price = price
            result.tp1_pnl_percent = pnl_percent
        elif tp_level == 'TP2' and not result.tp2_hit:
            result.tp2_hit = True
            result.tp2_timestamp = timestamp
            result.tp2_price = price
            result.tp2_pnl_percent = pnl_percent
        elif tp_level == 'TP3' and not result.tp3_hit:
            result.tp3_hit = True
            result.tp3_timestamp = timestamp
            result.tp3_price = price
            result.tp3_pnl_percent = pnl_percent
    
    # Check if all TPs are complete
    # **Feature: trade-enhancements, Property 11: All TPs Complete Detection**
    # **Validates: Requirements 3.5**
    result.all_tps_complete = result.tp1_hit and result.tp2_hit and result.tp3_hit
    
    return result
