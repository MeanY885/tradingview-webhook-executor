"""Oanda indicator-specific parser for TradingView alerts.

This parser handles the specific JSON format from Oanda forex indicators.

TRADE LIFECYCLE:
- Entry signal (bull_entry/bear_entry) creates a new trade
- All subsequent signals for the same symbol belong to that trade
- Trade closes when:
  - position_size = 0 (actual position closed - highest priority)
  - Final TP hit (based on tp_count from SymbolConfig)
  - Final SL hit (based on sl_count from SymbolConfig)
  - EXIT signal received

TRADINGVIEW ALERT MESSAGE EXAMPLES:

Bull Entry:
{"symbol": "{{ticker}}", "signal_type": "bull_entry", "entry_price": "{{plot_1}}", 
 "stop_loss": "{{plot_2}}", "take_profit_1": "{{plot_3}}", "take_profit_2": "{{plot_4}}", 
 "take_profit_3": "{{plot_5}}", "tp_count": "{{plot_10}}"}

Bear Entry:
{"symbol": "{{ticker}}", "signal_type": "bear_entry", "entry_price": "{{plot_1}}", 
 "stop_loss": "{{plot_2}}", "take_profit_1": "{{plot_3}}", "take_profit_2": "{{plot_4}}", 
 "take_profit_3": "{{plot_5}}", "tp_count": "{{plot_10}}"}

TP1 Hit (Long):
{"symbol": "{{ticker}}", "signal_type": "tp1", "market_position": "long", "exit_price": "{{close}}"}

TP2 Hit (Long):
{"symbol": "{{ticker}}", "signal_type": "tp2", "market_position": "long", "exit_price": "{{close}}"}

TP3 Hit (Long):
{"symbol": "{{ticker}}", "signal_type": "tp3", "market_position": "long", "exit_price": "{{close}}"}

Stop Loss:
{"symbol": "{{ticker}}", "signal_type": "stop_loss", "exit_price": "{{close}}"}

Manual Exit:
{"symbol": "{{ticker}}", "signal_type": "exit", "exit_price": "{{close}}"}

NOTE: For short positions, use "market_position": "short" in TP alerts.
"""
import json
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class OandaSignalType(Enum):
    """Signal types for Oanda indicator alerts."""
    BULL_ENTRY = "bull_entry"
    BEAR_ENTRY = "bear_entry"
    TP1 = "tp1"
    TP2 = "tp2"
    TP3 = "tp3"
    SL1 = "sl1"
    SL2 = "sl2"
    SL3 = "sl3"
    STOP_LOSS = "sl"  # Generic SL (same as SL1)
    EXIT = "exit"
    UNKNOWN = "unknown"


@dataclass
class OandaParsedSignal:
    """Parsed Oanda indicator signal."""
    # Core fields
    symbol: str
    signal_type: OandaSignalType
    action: str  # 'buy' or 'sell'
    quantity: float
    
    # Direction
    direction: str  # 'long' or 'short'
    is_entry: bool
    is_exit: bool
    
    # Prices
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None
    take_profit_3: Optional[float] = None
    
    # TP configuration
    tp_count: int = 1
    
    # For exits - which TP level was hit
    tp_level: Optional[str] = None  # 'TP1', 'TP2', 'TP3', 'SL'
    
    # Should this close the entire position?
    closes_position: bool = False
    
    # Raw data
    raw_payload: Optional[Dict[str, Any]] = None


class OandaIndicatorParser:
    """Parser for Oanda forex indicator alerts from TradingView."""
    
    @staticmethod
    def can_parse(raw_payload: dict) -> bool:
        """Check if this parser can handle the payload.
        
        Returns True if the payload has the Oanda indicator format markers:
        - Has 'signal_type' field
        - signal_type is one of the valid types
        """
        if not raw_payload or not isinstance(raw_payload, dict):
            return False
        
        signal_type = str(raw_payload.get('signal_type', '')).lower()
        
        valid_signal_types = [
            'bull_entry', 'bear_entry',
            'tp1', 'tp2', 'tp3',
            'sl', 'sl1', 'sl2', 'sl3',
            'stop_loss', 'stoploss',
            'exit', 'close'
        ]
        
        return signal_type in valid_signal_types
    
    @staticmethod
    def parse(raw_payload: dict) -> OandaParsedSignal:
        """Parse an Oanda indicator alert.
        
        Handles multiple payload formats:
        1. Simple format: symbol, entry_price, quantity, take_profit_1, etc.
        2. TradingView format: ticker, close, order_contracts, plot_0/plot_1, etc.
        
        Args:
            raw_payload: Raw webhook payload dictionary
            
        Returns:
            OandaParsedSignal with parsed data
        """
        # Extract symbol (try multiple field names)
        symbol = (
            str(raw_payload.get('symbol', '') or raw_payload.get('ticker', '')).upper()
        )
        
        # Parse signal_type
        signal_type_str = str(raw_payload.get('signal_type', '')).lower()
        signal_type = OandaIndicatorParser._parse_signal_type(signal_type_str)
        
        # Determine direction and entry/exit status
        direction, is_entry, is_exit = OandaIndicatorParser._determine_direction(
            signal_type, raw_payload
        )
        
        # Determine action (buy/sell)
        action = OandaIndicatorParser._determine_action(signal_type, direction, is_entry)
        
        # Parse quantity - try multiple field names
        # order_contracts from TradingView, quantity from simple format
        quantity = OandaIndicatorParser._parse_float(raw_payload.get('quantity'))
        if quantity is None or quantity == 0:
            quantity = OandaIndicatorParser._parse_float(raw_payload.get('order_contracts'))
        if quantity is None or quantity == 0:
            quantity = OandaIndicatorParser._parse_float(raw_payload.get('position_size'))
        if quantity is None:
            quantity = 0
        
        # Parse prices - try multiple field names
        # For entries: entry_price, order_price, close (current price)
        entry_price = OandaIndicatorParser._parse_float(raw_payload.get('entry_price'))
        if entry_price is None:
            entry_price = OandaIndicatorParser._parse_float(raw_payload.get('order_price'))
        if entry_price is None:
            entry_price = OandaIndicatorParser._parse_float(raw_payload.get('close'))
        
        # For exits: exit_price, order_price, close
        exit_price = OandaIndicatorParser._parse_float(raw_payload.get('exit_price'))
        if exit_price is None and is_exit:
            exit_price = OandaIndicatorParser._parse_float(raw_payload.get('order_price'))
        if exit_price is None and is_exit:
            exit_price = OandaIndicatorParser._parse_float(raw_payload.get('close'))
        
        # Parse stop loss - try multiple field names
        stop_loss = OandaIndicatorParser._parse_float(raw_payload.get('stop_loss'))
        if stop_loss is None:
            stop_loss = OandaIndicatorParser._parse_float(raw_payload.get('exit_stop'))
        
        # Parse take profit levels - try multiple field names
        take_profit_1 = OandaIndicatorParser._parse_float(raw_payload.get('take_profit_1'))
        if take_profit_1 is None:
            take_profit_1 = OandaIndicatorParser._parse_float(raw_payload.get('exit_limit'))
        # Also check plot_0/plot_1 which some indicators use for TP levels
        if take_profit_1 is None:
            # plot_1 often contains the TP price in some indicator setups
            take_profit_1 = OandaIndicatorParser._parse_float(raw_payload.get('plot_1'))
        
        take_profit_2 = OandaIndicatorParser._parse_float(raw_payload.get('take_profit_2'))
        take_profit_3 = OandaIndicatorParser._parse_float(raw_payload.get('take_profit_3'))
        
        # Parse tp_count
        tp_count = OandaIndicatorParser._parse_int(raw_payload.get('tp_count'), 1)
        
        # Determine TP level for exits
        tp_level = OandaIndicatorParser._determine_tp_level(signal_type)
        
        # Determine if this closes the position
        closes_position = OandaIndicatorParser._should_close_position(
            signal_type, tp_count, tp_level
        )
        
        logger.info(
            f"Parsed Oanda signal: {symbol} {signal_type.value} "
            f"direction={direction} is_entry={is_entry} is_exit={is_exit} "
            f"tp_count={tp_count} closes_position={closes_position}"
        )
        
        return OandaParsedSignal(
            symbol=symbol,
            signal_type=signal_type,
            action=action,
            quantity=quantity,
            direction=direction,
            is_entry=is_entry,
            is_exit=is_exit,
            entry_price=entry_price,
            exit_price=exit_price,
            stop_loss=stop_loss,
            take_profit_1=take_profit_1,
            take_profit_2=take_profit_2,
            take_profit_3=take_profit_3,
            tp_count=tp_count,
            tp_level=tp_level,
            closes_position=closes_position,
            raw_payload=raw_payload
        )
    
    @staticmethod
    def _parse_signal_type(signal_type_str: str) -> OandaSignalType:
        """Parse signal type string to enum."""
        mapping = {
            'bull_entry': OandaSignalType.BULL_ENTRY,
            'bear_entry': OandaSignalType.BEAR_ENTRY,
            'tp1': OandaSignalType.TP1,
            'tp2': OandaSignalType.TP2,
            'tp3': OandaSignalType.TP3,
            'sl': OandaSignalType.STOP_LOSS,
            'sl1': OandaSignalType.SL1,
            'sl2': OandaSignalType.SL2,
            'sl3': OandaSignalType.SL3,
            'stop_loss': OandaSignalType.STOP_LOSS,
            'stoploss': OandaSignalType.STOP_LOSS,
            'exit': OandaSignalType.EXIT,
            'close': OandaSignalType.EXIT,
        }
        return mapping.get(signal_type_str, OandaSignalType.UNKNOWN)
    
    @staticmethod
    def _determine_direction(
        signal_type: OandaSignalType, 
        raw_payload: dict
    ) -> tuple:
        """Determine trade direction and entry/exit status.
        
        Returns:
            tuple: (direction, is_entry, is_exit)
        """
        is_entry = signal_type in [OandaSignalType.BULL_ENTRY, OandaSignalType.BEAR_ENTRY]
        is_exit = signal_type in [
            OandaSignalType.TP1, OandaSignalType.TP2, OandaSignalType.TP3,
            OandaSignalType.STOP_LOSS, OandaSignalType.SL1, OandaSignalType.SL2, OandaSignalType.SL3,
            OandaSignalType.EXIT
        ]
        
        # Determine direction
        if signal_type == OandaSignalType.BULL_ENTRY:
            direction = 'long'
        elif signal_type == OandaSignalType.BEAR_ENTRY:
            direction = 'short'
        else:
            # For exits, get direction from market_position field
            market_position = str(raw_payload.get('market_position', '')).lower()
            if market_position == 'long':
                direction = 'long'
            elif market_position == 'short':
                direction = 'short'
            else:
                # Default to long if not specified
                direction = 'long'
                logger.warning(f"Could not determine direction, defaulting to 'long'")
        
        return direction, is_entry, is_exit
    
    @staticmethod
    def _determine_action(
        signal_type: OandaSignalType, 
        direction: str, 
        is_entry: bool
    ) -> str:
        """Determine buy/sell action.
        
        For entries:
        - bull_entry (long) -> buy
        - bear_entry (short) -> sell
        
        For exits:
        - Closing a long -> sell
        - Closing a short -> buy
        """
        if is_entry:
            return 'buy' if direction == 'long' else 'sell'
        else:
            # Exits are opposite of the position direction
            return 'sell' if direction == 'long' else 'buy'
    
    @staticmethod
    def _determine_tp_level(signal_type: OandaSignalType) -> Optional[str]:
        """Determine TP/SL level string for exits."""
        mapping = {
            OandaSignalType.TP1: 'TP1',
            OandaSignalType.TP2: 'TP2',
            OandaSignalType.TP3: 'TP3',
            OandaSignalType.STOP_LOSS: 'SL',
            OandaSignalType.SL1: 'SL1',
            OandaSignalType.SL2: 'SL2',
            OandaSignalType.SL3: 'SL3',
            OandaSignalType.EXIT: 'EXIT',
        }
        return mapping.get(signal_type)
    
    @staticmethod
    def _should_close_position(
        signal_type: OandaSignalType, 
        tp_count: int, 
        tp_level: Optional[str]
    ) -> bool:
        """Determine if this signal MIGHT close the position.
        
        NOTE: This is a preliminary check. The actual closing decision is made
        by the trade grouping service using SymbolConfig (user-defined tp_count/sl_count).
        
        This method returns True for:
        - EXIT signal (always closes)
        - Any SL signal (final decision based on sl_count in SymbolConfig)
        - Any TP signal that matches or exceeds tp_count from payload
        
        The trade grouping service will make the final decision based on
        the user's SymbolConfig for this symbol.
        """
        # EXIT always closes
        if signal_type == OandaSignalType.EXIT:
            return True
        
        # SL signals - let trade grouping decide based on sl_count config
        # For now, mark as potentially closing
        if signal_type in [OandaSignalType.STOP_LOSS, OandaSignalType.SL1, 
                           OandaSignalType.SL2, OandaSignalType.SL3]:
            # If tp_count from payload suggests this is final SL, mark as closing
            # Otherwise, trade grouping will check SymbolConfig
            return True  # Conservative: assume SL closes unless config says otherwise
        
        # For TP signals, check if this might be the final TP
        # Trade grouping will verify against SymbolConfig
        if signal_type == OandaSignalType.TP1 and tp_count <= 1:
            return True
        if signal_type == OandaSignalType.TP2 and tp_count <= 2:
            return True
        if signal_type == OandaSignalType.TP3 and tp_count <= 3:
            return True
        
        return False
    
    @staticmethod
    def _parse_float(value, default: float = None) -> Optional[float]:
        """Safely parse a value to float."""
        if value is None:
            return default
        
        # Handle "null" string
        if isinstance(value, str):
            if value.lower() in ('null', 'none', ''):
                return default
            try:
                return float(value.strip())
            except ValueError:
                return default
        
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def _parse_int(value, default: int = 1) -> int:
        """Safely parse a value to int."""
        if value is None:
            return default
        
        if isinstance(value, str):
            if value.lower() in ('null', 'none', ''):
                return default
            try:
                return int(float(value.strip()))
            except ValueError:
                return default
        
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def to_normalized_params(parsed: OandaParsedSignal) -> dict:
        """Convert parsed signal to normalized webhook params format.
        
        This allows the parsed signal to be used with existing webhook processing.
        """
        # Determine order_type based on signal
        if parsed.is_entry:
            order_type = 'enter_long' if parsed.direction == 'long' else 'enter_short'
        elif parsed.closes_position:
            order_type = 'exit_long' if parsed.direction == 'long' else 'exit_short'
        else:
            order_type = 'reduce_long' if parsed.direction == 'long' else 'reduce_short'
        
        # Use exit_price for exits, entry_price for entries
        price = parsed.exit_price if parsed.is_exit else parsed.entry_price
        
        # Extract test_mode from raw payload if present
        test_mode = False
        if parsed.raw_payload:
            test_mode_val = parsed.raw_payload.get('test_mode')
            if isinstance(test_mode_val, bool):
                test_mode = test_mode_val
            elif isinstance(test_mode_val, str):
                test_mode = test_mode_val.lower() == 'true'
        
        return {
            'symbol': parsed.symbol,
            'action': parsed.action,
            'order_type': 'market',  # Oanda indicator signals are market orders
            'quantity': parsed.quantity,
            'price': price,
            'stop_loss': parsed.stop_loss,
            'take_profit': parsed.take_profit_1,
            'trailing_stop_pct': None,
            'leverage': None,
            'test_mode': test_mode,
            'metadata': {
                'signal_type': parsed.signal_type.value,
                'market_position': parsed.direction,
                'position_size': 0 if parsed.closes_position else None,
                'tp_count': parsed.tp_count,
                'tp_level': parsed.tp_level,
                'closes_position': parsed.closes_position,
                'take_profit_levels': {
                    'take_profit_1': parsed.take_profit_1,
                    'take_profit_2': parsed.take_profit_2,
                    'take_profit_3': parsed.take_profit_3,
                },
                # Internal order_type for grouping
                '_internal_order_type': order_type,
            }
        }
