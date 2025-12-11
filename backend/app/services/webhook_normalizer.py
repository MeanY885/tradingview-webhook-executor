"""Webhook normalizer service for robust JSON parsing of TradingView webhooks.

This module provides a centralized service for normalizing the complex, nested JSON
structure from TradingView webhooks into a flat, consistent structure for processing.
"""
import json
import re
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class AlertType(Enum):
    """Types of alerts that can be detected from webhooks."""
    ENTRY = "ENTRY"
    TP1 = "TP1"
    TP2 = "TP2"
    TP3 = "TP3"
    TP4 = "TP4"
    TP5 = "TP5"
    STOP_LOSS = "SL"
    PARTIAL = "PARTIAL"
    EXIT = "EXIT"
    UNKNOWN = "UNKNOWN"


@dataclass
class NormalizedWebhook:
    """Normalized webhook with guaranteed field types.
    
    This dataclass provides a consistent structure for webhook data regardless
    of the source format variations from TradingView strategies.
    
    Requirements: 1.1, 1.2, 2.2, 2.5, 4.1, 4.2, 5.1, 5.2
    """
    # Core identification
    symbol: str
    action: str  # 'buy' or 'sell'
    order_type: str  # 'enter_long', 'reduce_long', 'exit_long', etc.
    alert_type: str  # 'ENTRY', 'TP1', 'TP2', 'TP3', 'SL', 'PARTIAL', 'EXIT', 'UNKNOWN'
    
    # Prices (always float or None)
    order_price: Optional[float] = None
    entry_price: Optional[float] = None  # For entries
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None  # TP price from exit_limit or take_profit_price
    
    # Quantities (always float or None)
    order_contracts: Optional[float] = None
    position_size: Optional[float] = None  # Remaining after this action
    
    # Position state
    market_position: str = ""  # 'long', 'short', 'flat'
    prev_market_position: str = ""  # Previous position state (for detecting entry/exit)
    is_position_closed: bool = False  # True if position_size=0 AND market_position=flat
    
    # Trade parameters
    leverage: Optional[float] = None
    pyramiding: Optional[int] = None
    
    # Exit strategy fields (TradingView strategy format)
    # Requirements: 1.1, 1.2, 2.2, 5.1, 5.2
    exit_stop: Optional[float] = None  # TradingView exit_stop field
    exit_limit: Optional[float] = None  # TradingView exit_limit field
    exit_loss_ticks: Optional[float] = None  # Exit loss in ticks
    exit_profit_ticks: Optional[float] = None  # Exit profit in ticks
    exit_trail_price: Optional[float] = None  # Trailing stop price
    exit_trail_offset: Optional[float] = None  # Trailing stop offset
    
    # Custom indicator values (plot_0, plot_1, etc.)
    # Requirements: 2.5
    plot_values: Dict[str, float] = field(default_factory=dict)

    # TradeAlgo Elite multi-TP support
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None
    take_profit_3: Optional[float] = None
    take_profit_4: Optional[float] = None
    take_profit_5: Optional[float] = None
    tp_count: Optional[int] = None

    # TradeAlgo Elite technical indicators (optional, for logging/analysis)
    atr_value: Optional[float] = None
    sl_dist_pips: Optional[float] = None

    # Bull/Bear signal indicators (alternative direction detection)
    is_bull: Optional[bool] = None
    is_bear: Optional[bool] = None
    is_bull_exit: Optional[bool] = None
    is_bear_exit: Optional[bool] = None

    # Metadata
    timestamp: Optional[datetime] = None
    order_id: Optional[str] = None
    order_comment: Optional[str] = None

    # Raw data for debugging
    raw_payload: Dict[str, Any] = field(default_factory=dict)


class WebhookNormalizer:
    """Normalize TradingView webhook payloads into consistent structure.
    
    This service handles the complex, nested JSON structure from TradingView
    webhooks where critical parameters are split between the main payload
    and an embedded `order_alert_message` string.
    """
    
    @staticmethod
    def parse_alert_message(alert_message: str) -> Dict[str, Any]:
        """
        Parse the order_alert_message field which contains embedded parameters.
        
        Handles malformed JSON like:
        - Missing braces: '"key": "value", "key2": "value2"'
        - Extra quotes: '""key": "value"'
        - Trailing commas
        
        Args:
            alert_message: The raw alert message string
            
        Returns:
            dict: Parsed parameters from the alert message, empty dict on failure
            
        Requirements: 4.1, 4.2, 5.1
        """
        if not alert_message or not isinstance(alert_message, str):
            return {}
        
        # Try parsing as-is first (in case it's valid JSON)
        try:
            result = json.loads(alert_message)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass
        
        # Handle malformed JSON
        cleaned = alert_message.strip()
        
        # Remove leading/trailing quotes if present (but not part of JSON structure)
        if cleaned.startswith('"') and not cleaned.startswith('"{'):
            cleaned = cleaned[1:]
        if cleaned.endswith('",') or (cleaned.endswith('"') and not cleaned.endswith('}"')):
            cleaned = cleaned.rstrip('",')
        
        # Handle double quotes at start (e.g., ""margin_mode" -> "margin_mode")
        while cleaned.startswith('""'):
            cleaned = cleaned[1:]
        
        # Handle case where string starts with "key": (missing opening brace)
        # Pattern: starts with "word": which indicates a JSON key-value pair
        if re.match(r'^"[^"]+"\s*:', cleaned):
            cleaned = '{' + cleaned
        
        # Add braces if missing
        if not cleaned.startswith('{'):
            cleaned = '{' + cleaned
        if not cleaned.endswith('}'):
            cleaned = cleaned.rstrip(',') + '}'
        
        try:
            result = json.loads(cleaned)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass
        
        # If still can't parse, try to extract key-value pairs manually
        params = {}
        # Match patterns like "key": "value" or "key": value
        pattern = r'"([^"]+)":\s*"?([^",}]+)"?'
        matches = re.findall(pattern, alert_message)
        for key, value in matches:
            value = value.strip()
            # Try to convert to appropriate type
            if value.lower() == 'true':
                params[key] = True
            elif value.lower() == 'false':
                params[key] = False
            elif value.replace('.', '', 1).replace('-', '', 1).isdigit():
                try:
                    params[key] = float(value) if '.' in value else int(value)
                except ValueError:
                    params[key] = value
            else:
                params[key] = value
        
        return params
    
    @staticmethod
    def serialize_alert_message(params: Dict[str, Any]) -> str:
        """
        Serialize parameters back to alert message format.
        
        This is the inverse of parse_alert_message for round-trip testing.
        
        Args:
            params: Dictionary of parameters to serialize
            
        Returns:
            str: JSON string representation
        """
        if not params:
            return ""
        return json.dumps(params)

    
    @staticmethod
    def normalize(raw_payload: dict) -> NormalizedWebhook:
        """
        Parse and normalize webhook payload from any TradingView strategy format.
        
        Handles:
        - Nested order_alert_message parsing (JSON string inside JSON)
        - Field name variations (order_contracts vs contracts vs quantity)
        - String-to-number conversions for prices/quantities
        - Missing field defaults
        
        Args:
            raw_payload: Raw webhook payload dictionary
            
        Returns:
            NormalizedWebhook with guaranteed fields
            
        Requirements: 1.1, 5.1, 5.2
        """
        if not raw_payload:
            raw_payload = {}
        
        # Parse embedded alert_message if present
        alert_message = raw_payload.get('order_alert_message', '')
        alert_params = WebhookNormalizer.parse_alert_message(alert_message)
        
        # Extract symbol (try multiple field names)
        # Requirements 2.3: ticker is alias for symbol, symbol takes precedence
        symbol = ''
        for field_name in ['symbol', 'instrument', 'ticker']:
            val = raw_payload.get(field_name)
            if val and isinstance(val, str) and not val.startswith('{{'):
                symbol = val.upper()
                break
        
        # Extract action (try multiple field names)
        action = ''
        for field in ['action', 'side', 'order_action']:
            val = raw_payload.get(field)
            if val and isinstance(val, str) and not val.startswith('{{'):
                action = val.lower()
                break
        
        # Extract order_type from alert_params (primary) or raw_payload (fallback)
        order_type = alert_params.get('order_type', '')
        if not order_type:
            order_type = raw_payload.get('order_type', '')
        if isinstance(order_type, str):
            order_type = order_type.lower()
        
        # Extract order_contracts (try multiple field names)
        # Use _get_first_valid to handle 0 values correctly
        order_contracts_raw = WebhookNormalizer._get_first_valid(
            raw_payload.get('order_contracts'),
            raw_payload.get('contracts'),
            raw_payload.get('quantity'),
            alert_params.get('order_contracts'),
            alert_params.get('contracts'),
            alert_params.get('quantity')
        )
        order_contracts = WebhookNormalizer._parse_float(order_contracts_raw)
        
        # Extract position_size (use _get_first_valid to handle 0 values correctly)
        position_size_raw = WebhookNormalizer._get_first_valid(
            raw_payload.get('position_size'),
            alert_params.get('position_size')
        )
        position_size = WebhookNormalizer._parse_float(position_size_raw)
        
        # Extract market_position and prev_market_position
        market_position = str(raw_payload.get('market_position', '') or 
                             alert_params.get('market_position', '')).lower()
        prev_market_position = str(raw_payload.get('prev_market_position', '') or 
                                   alert_params.get('prev_market_position', '')).lower()
        
        # Determine if position is closed
        is_position_closed = (
            position_size is not None and position_size == 0 and 
            market_position == 'flat'
        )
        
        # Extract prices (use _get_first_valid to handle 0 values correctly)
        order_price = WebhookNormalizer._parse_float(
            WebhookNormalizer._get_first_valid(
                raw_payload.get('order_price'),
                raw_payload.get('price')
            )
        )
        entry_price = WebhookNormalizer._parse_float(
            WebhookNormalizer._get_first_valid(
                raw_payload.get('entry_price'),
                raw_payload.get('EntryPrice'),  # TradeAlgo Elite Indicator
                raw_payload.get('Long Entry Price'),  # TradeAlgo Elite Backtester
                raw_payload.get('Short Entry Price'),  # TradeAlgo Elite Backtester
                raw_payload.get('position_avg_price'),
                alert_params.get('entry_price')
            )
        )
        # Extract exit strategy fields first (Requirements 1.1, 1.2, 2.1, 2.2)
        exit_stop = WebhookNormalizer._parse_float(
            WebhookNormalizer._get_first_valid(
                raw_payload.get('exit_stop'),
                alert_params.get('exit_stop')
            )
        )
        exit_limit = WebhookNormalizer._parse_float(
            WebhookNormalizer._get_first_valid(
                raw_payload.get('exit_limit'),
                alert_params.get('exit_limit')
            )
        )
        exit_loss_ticks = WebhookNormalizer._parse_float(
            WebhookNormalizer._get_first_valid(
                raw_payload.get('exit_loss_ticks'),
                alert_params.get('exit_loss_ticks')
            )
        )
        exit_profit_ticks = WebhookNormalizer._parse_float(
            WebhookNormalizer._get_first_valid(
                raw_payload.get('exit_profit_ticks'),
                alert_params.get('exit_profit_ticks')
            )
        )
        
        # Extract trailing stop fields (Requirements 2.2, 5.1, 5.2)
        exit_trail_price = WebhookNormalizer._parse_float(
            WebhookNormalizer._get_first_valid(
                raw_payload.get('exit_trail_price'),
                alert_params.get('exit_trail_price')
            )
        )
        exit_trail_offset = WebhookNormalizer._parse_float(
            WebhookNormalizer._get_first_valid(
                raw_payload.get('exit_trail_offset'),
                alert_params.get('exit_trail_offset')
            )
        )
        
        # Extract stop_loss_price with exit_stop mapping (Requirements 2.1)
        # exit_stop maps to stop_loss_price if stop_loss_price not explicitly set
        stop_loss_price = WebhookNormalizer._parse_float(
            WebhookNormalizer._get_first_valid(
                alert_params.get('stop_loss_price'),
                raw_payload.get('stop_loss_price'),
                raw_payload.get('stop_loss'),
                raw_payload.get('StopLoss'),  # TradeAlgo Elite Indicator
                raw_payload.get('Long Stop Price'),  # TradeAlgo Elite Backtester
                raw_payload.get('Short Stop Price')  # TradeAlgo Elite Backtester
            )
        )
        # If no explicit stop_loss_price, use exit_stop
        if stop_loss_price is None and exit_stop is not None:
            stop_loss_price = exit_stop
        
        # Extract take_profit_price with exit_limit mapping (Requirements 2.1)
        # exit_limit maps to take_profit_price if take_profit_price not explicitly set
        take_profit_price = WebhookNormalizer._parse_float(
            WebhookNormalizer._get_first_valid(
                alert_params.get('take_profit_price'),
                raw_payload.get('take_profit_price'),
                raw_payload.get('take_profit')
            )
        )
        # If no explicit take_profit_price, use exit_limit
        if take_profit_price is None and exit_limit is not None:
            take_profit_price = exit_limit

        # ============================================================
        # TRADEALGO ELITE MULTI-TP EXTRACTION
        # Extract individual take profit levels (TP1-TP5) for TradeAlgo Elite
        # ============================================================
        take_profit_1 = WebhookNormalizer._parse_float(
            WebhookNormalizer._get_first_valid(
                raw_payload.get('take_profit_1'),
                raw_payload.get('TakeProfit1'),  # TradeAlgo Elite Indicator
                raw_payload.get('Long TP-1 Price'),  # TradeAlgo Elite Backtester
                raw_payload.get('Short TP-1 Price'),
                alert_params.get('take_profit_1'),
                alert_params.get('tp_1_price'),  # Blofin format
                raw_payload.get('tp_1_price')
            )
        )
        take_profit_2 = WebhookNormalizer._parse_float(
            WebhookNormalizer._get_first_valid(
                raw_payload.get('take_profit_2'),
                raw_payload.get('TakeProfit2'),
                raw_payload.get('Long TP-2 Price'),
                raw_payload.get('Short TP-2 Price'),
                alert_params.get('take_profit_2'),
                alert_params.get('tp_2_price'),  # Blofin format
                raw_payload.get('tp_2_price')
            )
        )
        take_profit_3 = WebhookNormalizer._parse_float(
            WebhookNormalizer._get_first_valid(
                raw_payload.get('take_profit_3'),
                raw_payload.get('TakeProfit3'),
                raw_payload.get('Long TP-3 Price'),
                raw_payload.get('Short TP-3 Price'),
                alert_params.get('take_profit_3'),
                alert_params.get('tp_3_price'),  # Blofin format
                raw_payload.get('tp_3_price')
            )
        )
        take_profit_4 = WebhookNormalizer._parse_float(
            WebhookNormalizer._get_first_valid(
                raw_payload.get('take_profit_4'),
                raw_payload.get('TakeProfit4'),
                raw_payload.get('Long TP-4 Price'),
                raw_payload.get('Short TP-4 Price'),
                alert_params.get('take_profit_4'),
                alert_params.get('tp_4_price'),  # Blofin format
                raw_payload.get('tp_4_price')
            )
        )
        take_profit_5 = WebhookNormalizer._parse_float(
            WebhookNormalizer._get_first_valid(
                raw_payload.get('take_profit_5'),
                raw_payload.get('TakeProfit5'),
                raw_payload.get('Long TP-5 Price'),
                raw_payload.get('Short TP-5 Price'),
                alert_params.get('take_profit_5'),
                alert_params.get('tp_5_price'),  # Blofin format
                raw_payload.get('tp_5_price')
            )
        )

        # Use first TP as take_profit_price if not already set
        if take_profit_price is None and take_profit_1 is not None:
            take_profit_price = take_profit_1

        # Extract tp_count
        tp_count = WebhookNormalizer._parse_int(
            WebhookNormalizer._get_first_valid(
                raw_payload.get('tp_count'),
                raw_payload.get('tpCount'),
                alert_params.get('tp_count')
            )
        )

        # Extract TradeAlgo technical indicators (optional)
        atr_value = WebhookNormalizer._parse_float(
            WebhookNormalizer._get_first_valid(
                raw_payload.get('atr_value'),
                raw_payload.get('AtrValue'),
                alert_params.get('atr_value')
            )
        )
        sl_dist_pips = WebhookNormalizer._parse_float(
            WebhookNormalizer._get_first_valid(
                raw_payload.get('sl_dist_pips'),
                raw_payload.get('slDistInPips'),
                alert_params.get('sl_dist_pips')
            )
        )

        # Extract Bull/Bear indicators for alternative direction detection
        is_bull = WebhookNormalizer._parse_bool(
            WebhookNormalizer._get_first_valid(
                raw_payload.get('is_bull'),
                raw_payload.get('Bull'),
                alert_params.get('is_bull')
            )
        )
        is_bear = WebhookNormalizer._parse_bool(
            WebhookNormalizer._get_first_valid(
                raw_payload.get('is_bear'),
                raw_payload.get('Bear'),
                alert_params.get('is_bear')
            )
        )
        is_bull_exit = WebhookNormalizer._parse_bool(
            WebhookNormalizer._get_first_valid(
                raw_payload.get('is_bull_exit'),
                raw_payload.get('Bull Exit'),
                alert_params.get('is_bull_exit')
            )
        )
        is_bear_exit = WebhookNormalizer._parse_bool(
            WebhookNormalizer._get_first_valid(
                raw_payload.get('is_bear_exit'),
                raw_payload.get('Bear Exit'),
                alert_params.get('is_bear_exit')
            )
        )

        # Extract plot values (Requirements 2.5)
        # Extract fields matching pattern plot_N (where N is a digit)
        plot_values = {}
        for key, value in raw_payload.items():
            if key.startswith('plot_') and len(key) > 5 and key[5:].isdigit():
                parsed_value = WebhookNormalizer._parse_float(value)
                if parsed_value is not None:
                    plot_values[key] = parsed_value
        # Also check alert_params for plot values
        for key, value in alert_params.items():
            if key.startswith('plot_') and len(key) > 5 and key[5:].isdigit():
                if key not in plot_values:  # raw_payload takes precedence
                    parsed_value = WebhookNormalizer._parse_float(value)
                    if parsed_value is not None:
                        plot_values[key] = parsed_value
        
        # Extract leverage
        leverage = WebhookNormalizer._parse_float(
            WebhookNormalizer._get_first_valid(
                alert_params.get('leverage'),
                raw_payload.get('leverage')
            )
        )
        
        # Extract pyramiding
        pyramiding = WebhookNormalizer._parse_int(
            WebhookNormalizer._get_first_valid(
                alert_params.get('pyramiding'),
                raw_payload.get('pyramiding')
            )
        )
        
        # Extract metadata
        order_id = raw_payload.get('order_id')
        order_comment = raw_payload.get('order_comment')
        
        # Parse timestamp
        timestamp = None
        ts_str = raw_payload.get('timestamp')
        if ts_str:
            try:
                timestamp = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                pass
        
        # Detect alert type (will be implemented in detect_alert_type)
        alert_type = WebhookNormalizer.detect_alert_type_from_data(
            order_type, order_comment, order_id
        )
        
        # ============================================================
        # INDICATOR FALLBACK LOGIC
        # When strategy placeholders aren't populated (indicators don't have access to {{strategy.*}}),
        # try to infer trade data from signal_type field or plot values.
        # ============================================================
        
        # First check for explicit signal_type field (for indicator-based alerts)
        signal_type = str(raw_payload.get('signal_type', '') or alert_params.get('signal_type', '')).lower()
        
        if signal_type:
            logger.info(f"Found signal_type={signal_type} for {symbol}")
            
            # Map signal_type to action and alert_type
            if signal_type in ['bull_entry', 'bull', 'long', 'buy']:
                action = 'buy'
                order_type = 'enter_long'
                alert_type = AlertType.ENTRY.value
                market_position = 'long'
                logger.info(f"Mapped signal_type={signal_type} to buy/long entry")
            elif signal_type in ['bear_entry', 'bear', 'short', 'sell']:
                action = 'sell'
                order_type = 'enter_short'
                alert_type = AlertType.ENTRY.value
                market_position = 'short'
                logger.info(f"Mapped signal_type={signal_type} to sell/short entry")
            elif signal_type == 'tp1':
                alert_type = AlertType.TP1.value
                order_type = 'reduce'
                logger.info(f"Mapped signal_type={signal_type} to TP1")
            elif signal_type == 'tp2':
                alert_type = AlertType.TP2.value
                order_type = 'reduce'
                logger.info(f"Mapped signal_type={signal_type} to TP2")
            elif signal_type == 'tp3':
                alert_type = AlertType.TP3.value
                order_type = 'reduce'
                logger.info(f"Mapped signal_type={signal_type} to TP3")
            elif signal_type == 'tp4':
                alert_type = AlertType.TP4.value
                order_type = 'reduce'
                logger.info(f"Mapped signal_type={signal_type} to TP4")
            elif signal_type == 'tp5':
                alert_type = AlertType.TP5.value
                order_type = 'reduce'
                logger.info(f"Mapped signal_type={signal_type} to TP5")
            elif signal_type in ['stop_loss', 'sl', 'stoploss']:
                alert_type = AlertType.STOP_LOSS.value
                order_type = 'exit'
                logger.info(f"Mapped signal_type={signal_type} to STOP_LOSS")
            elif signal_type in ['exit', 'close', 'flat']:
                alert_type = AlertType.EXIT.value
                order_type = 'exit'
                logger.info(f"Mapped signal_type={signal_type} to EXIT")

        # Bull/Bear indicator fallback - if no signal_type but Bull/Bear indicators present
        if not signal_type and not action:
            if is_bull is True:
                action = 'buy'
                order_type = 'enter_long'
                alert_type = AlertType.ENTRY.value
                market_position = 'long'
                logger.info("Inferred bull entry from Bull indicator")
            elif is_bear is True:
                action = 'sell'
                order_type = 'enter_short'
                alert_type = AlertType.ENTRY.value
                market_position = 'short'
                logger.info("Inferred bear entry from Bear indicator")
            elif is_bull_exit is True:
                alert_type = AlertType.EXIT.value
                order_type = 'exit'
                logger.info("Inferred bull exit from Bull Exit indicator")
            elif is_bear_exit is True:
                alert_type = AlertType.EXIT.value
                order_type = 'exit'
                logger.info("Inferred bear exit from Bear Exit indicator")

        # Check if this looks like an unpopulated indicator alert
        # (action is empty or still a placeholder, but we have plot values)
        is_indicator_alert = (
            (not action or action.startswith('{{')) and 
            plot_values and 
            symbol
        )
        
        if is_indicator_alert:
            logger.info(f"Detected indicator-based alert for {symbol}, attempting to infer trade data from plots")
            
            # Try to infer action from plot_0 (common pattern: 1=long, -1=short, 0=flat)
            plot_0 = plot_values.get('plot_0')
            if plot_0 is not None and not action:
                if plot_0 == 1 or plot_0 == 1.0:
                    action = 'buy'
                    if not order_type:
                        order_type = 'enter_long'
                    if not alert_type or alert_type == AlertType.UNKNOWN.value:
                        alert_type = AlertType.ENTRY.value
                    logger.info(f"Inferred action=buy from plot_0={plot_0}")
                elif plot_0 == -1 or plot_0 == -1.0:
                    action = 'sell'
                    if not order_type:
                        order_type = 'enter_short'
                    if not alert_type or alert_type == AlertType.UNKNOWN.value:
                        alert_type = AlertType.ENTRY.value
                    logger.info(f"Inferred action=sell from plot_0={plot_0}")
                elif plot_0 == 0 or plot_0 == 0.0:
                    # Could be exit/close signal
                    if not alert_type or alert_type == AlertType.UNKNOWN.value:
                        alert_type = AlertType.EXIT.value
                    logger.info(f"Inferred exit signal from plot_0={plot_0}")
            
            # Try to use plot_1 as entry price if order_price not set
            plot_1 = plot_values.get('plot_1')
            if plot_1 is not None and order_price is None:
                order_price = plot_1
                logger.info(f"Using plot_1={plot_1} as order_price")
            
            # Fallback to close price if still no order_price
            if order_price is None:
                close_price = WebhookNormalizer._parse_float(raw_payload.get('close'))
                if close_price is not None:
                    order_price = close_price
                    logger.info(f"Using close={close_price} as order_price")
            
            # Try to use plot_2 as take_profit if available and not set
            plot_2 = plot_values.get('plot_2')
            if plot_2 is not None and take_profit_price is None:
                take_profit_price = plot_2
                logger.info(f"Using plot_2={plot_2} as take_profit_price")
            
            # Try to use plot_3 as stop_loss if available and not set
            plot_3 = plot_values.get('plot_3')
            if plot_3 is not None and stop_loss_price is None:
                stop_loss_price = plot_3
                logger.info(f"Using plot_3={plot_3} as stop_loss_price")
        
        return NormalizedWebhook(
            symbol=symbol,
            action=action,
            order_type=order_type,
            alert_type=alert_type,
            order_price=order_price,
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            order_contracts=order_contracts,
            position_size=position_size,
            market_position=market_position,
            prev_market_position=prev_market_position,
            is_position_closed=is_position_closed,
            leverage=leverage,
            pyramiding=pyramiding,
            exit_stop=exit_stop,
            exit_limit=exit_limit,
            exit_loss_ticks=exit_loss_ticks,
            exit_profit_ticks=exit_profit_ticks,
            exit_trail_price=exit_trail_price,
            exit_trail_offset=exit_trail_offset,
            plot_values=plot_values,
            # TradeAlgo Elite fields
            take_profit_1=take_profit_1,
            take_profit_2=take_profit_2,
            take_profit_3=take_profit_3,
            take_profit_4=take_profit_4,
            take_profit_5=take_profit_5,
            tp_count=tp_count,
            atr_value=atr_value,
            sl_dist_pips=sl_dist_pips,
            is_bull=is_bull,
            is_bear=is_bear,
            is_bull_exit=is_bull_exit,
            is_bear_exit=is_bear_exit,
            # Metadata
            timestamp=timestamp,
            order_id=order_id,
            order_comment=order_comment,
            raw_payload=raw_payload
        )
    
    @staticmethod
    def _parse_float(value) -> Optional[float]:
        """Safely parse a value to float.
        
        Handles:
        - None values → None
        - Numeric values (int, float) → float
        - String values → parsed float
        - Empty strings → None
        - Whitespace-only strings → None
        - Invalid strings → None (logged as warning)
        
        Requirements: 2.6
        """
        if value is None:
            return None
        
        # Handle string values
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            try:
                return float(stripped)
            except ValueError:
                logger.warning(f"Could not parse float from string: '{value}'")
                return None
        
        # Handle numeric values
        try:
            return float(value)
        except (ValueError, TypeError):
            logger.warning(f"Could not parse float from value: {value} (type: {type(value).__name__})")
            return None
    
    @staticmethod
    def _parse_int(value) -> Optional[int]:
        """Safely parse a value to int."""
        if value is None:
            return None
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_bool(value) -> Optional[bool]:
        """Safely parse a value to bool.

        Handles:
        - None values -> None
        - Boolean values -> bool
        - Numeric values (0/1, 0.0/1.0) -> bool
        - String values ('true', 'false', '1', '0') -> bool
        """
        if value is None:
            return None

        if isinstance(value, bool):
            return value

        if isinstance(value, (int, float)):
            return value == 1 or value == 1.0

        if isinstance(value, str):
            val_lower = value.strip().lower()
            if val_lower in ('true', '1', 'yes'):
                return True
            if val_lower in ('false', '0', 'no', ''):
                return False

        return None

    @staticmethod
    def _get_first_valid(*values):
        """Get the first non-None value from the arguments.
        
        Unlike using `or`, this correctly handles falsy values like 0 and 0.0.
        """
        for v in values:
            if v is not None:
                return v
        return None
    
    @staticmethod
    def detect_alert_type_from_data(order_type: str, order_comment: Optional[str], 
                                     order_id: Optional[str]) -> str:
        """
        Preliminary alert type detection used during normalization.
        
        This is a simplified version - full detection is in detect_alert_type().
        """
        order_type_lower = (order_type or '').lower()
        
        # Check for entry
        if 'enter_' in order_type_lower or 'entry_' in order_type_lower:
            return AlertType.ENTRY.value
        
        # For exits/reduces, check order_comment first (has precedence per Req 4.4)
        if order_comment:
            comment_upper = order_comment.upper()
            if 'TP1' in comment_upper:
                return AlertType.TP1.value
            if 'TP2' in comment_upper:
                return AlertType.TP2.value
            if 'TP3' in comment_upper:
                return AlertType.TP3.value
            if 'SL' in comment_upper or 'STOP' in comment_upper:
                return AlertType.STOP_LOSS.value
        
        # Fallback to order_id pattern matching
        if order_id:
            order_id_lower = order_id.lower()
            if '1st target' in order_id_lower:
                return AlertType.TP1.value
            if '2nd target' in order_id_lower:
                return AlertType.TP2.value
            if '3rd target' in order_id_lower:
                return AlertType.TP3.value
            if 'stop loss' in order_id_lower:
                return AlertType.STOP_LOSS.value
        
        # Check for reduce/exit without TP markers
        if 'reduce_' in order_type_lower:
            return AlertType.PARTIAL.value
        if 'exit_' in order_type_lower:
            return AlertType.EXIT.value
        
        return AlertType.UNKNOWN.value

    
    @staticmethod
    def detect_alert_type(normalized: NormalizedWebhook) -> AlertType:
        """
        Determine alert type from normalized data.
        
        Returns: ENTRY, TP1, TP2, TP3, STOP_LOSS, PARTIAL, EXIT, or UNKNOWN
        
        Logic:
        1. Check order_type for enter_* → ENTRY
        2. Check order_type for reduce_*/exit_* → exit type
        3. For exits, check order_comment first (TP1, TP2, TP3, SL) - has precedence
        4. Fallback to order_id pattern matching (1st Target, 2nd Target, etc.)
        5. If reduce without markers → PARTIAL
        
        Requirements: 4.1, 4.2, 4.3, 4.4
        """
        order_type = (normalized.order_type or '').lower()
        order_comment = normalized.order_comment
        order_id = normalized.order_id
        
        # Step 1: Check for entry
        if 'enter_' in order_type or 'entry_' in order_type:
            return AlertType.ENTRY
        
        # Step 2 & 3: For exits/reduces, check order_comment first (has precedence per Req 4.4)
        if order_comment:
            comment_upper = order_comment.upper()
            if 'TP1' in comment_upper:
                return AlertType.TP1
            if 'TP2' in comment_upper:
                return AlertType.TP2
            if 'TP3' in comment_upper:
                return AlertType.TP3
            if 'SL' in comment_upper or 'STOP' in comment_upper:
                return AlertType.STOP_LOSS
        
        # Step 4: Fallback to order_id pattern matching
        if order_id:
            order_id_lower = order_id.lower()
            if '1st target' in order_id_lower:
                return AlertType.TP1
            if '2nd target' in order_id_lower:
                return AlertType.TP2
            if '3rd target' in order_id_lower:
                return AlertType.TP3
            if 'stop loss' in order_id_lower:
                return AlertType.STOP_LOSS
        
        # Step 5: Check for reduce/exit without TP markers
        if 'reduce_' in order_type:
            return AlertType.PARTIAL
        if 'exit_' in order_type:
            return AlertType.EXIT
        
        return AlertType.UNKNOWN
