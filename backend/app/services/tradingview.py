"""TradingView webhook alert parsing service."""
import json
import re
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class TradingViewAlertParser:
    """Parse TradingView alert messages in multiple formats."""

    @staticmethod
    def parse_alert(raw_message: str) -> Dict:
        """
        Parse alert message (auto-detect JSON or text format).

        Returns:
            dict: Parsed trade parameters
                {
                    'symbol': str,
                    'action': str,  # 'buy' or 'sell'
                    'order_type': str,  # 'market', 'limit', 'stop', 'trailing'
                    'quantity': float,
                    'price': float (optional),
                    'stop_loss': float (optional),
                    'take_profit': float (optional),
                    'trailing_stop_pct': float (optional)
                }
        """
        # Try parsing as JSON first
        try:
            data = json.loads(raw_message)
            logger.debug(f"Parsed message as JSON: {list(data.keys())}")
            return TradingViewAlertParser._parse_json(data)
        except json.JSONDecodeError as e:
            # Not valid JSON, try to fix common issues
            logger.debug(f"JSON parse failed: {str(e)[:100]}, attempting to fix")
            fixed_data = TradingViewAlertParser._try_fix_malformed_json(raw_message)
            if fixed_data:
                logger.debug(f"Fixed malformed JSON, parsed keys: {list(fixed_data.keys())}")
                return TradingViewAlertParser._parse_json(fixed_data)
            # Fall back to text parsing
            logger.debug("Could not fix JSON, trying text format")
            pass
        except ValueError as e:
            # Valid JSON but invalid field values - provide clear error
            logger.warning(f"JSON field extraction error: {e}")
            raise ValueError(f"Invalid webhook data: {e}") from e

        # Fall back to text parsing only for non-JSON
        logger.debug("Attempting text format parsing")
        return TradingViewAlertParser._parse_text(raw_message)
    
    @staticmethod
    def _try_fix_malformed_json(raw_message: str) -> Optional[Dict]:
        """
        Attempt to fix common JSON malformations from TradingView webhooks.
        
        Common issues:
        - Trailing commas: "key": "value",}
        - Double commas: "key": "value",,
        - Unescaped quotes in strings
        - Missing closing braces
        - Double quotes at start of string values: ""value"
        """
        if not raw_message or not raw_message.strip().startswith('{'):
            return None
        
        cleaned = raw_message.strip()
        
        # Fix double commas and trailing commas before closing braces
        # Pattern: ,, -> ,
        cleaned = re.sub(r',\s*,', ',', cleaned)
        # Pattern: ,} -> }
        cleaned = re.sub(r',\s*}', '}', cleaned)
        # Pattern: ,] -> ]
        cleaned = re.sub(r',\s*]', ']', cleaned)
        
        # Fix ",", pattern (extra quote-comma-quote)
        cleaned = re.sub(r'",\s*",', '",', cleaned)
        
        # Fix "": "" pattern where value starts with double quote (e.g., ""margin_mode")
        # This pattern: ": ""key" -> ": "key"
        cleaned = re.sub(r':\s*""([^"]+)"', r': "\1"', cleaned)
        
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        
        # More aggressive fix: extract key-value pairs manually
        try:
            result = {}
            # Match "key": "value" or "key": number patterns
            # Also handle cases where value might have leading double quotes
            pattern = r'"([^"]+)"\s*:\s*"*([^",}\]]+)"*'
            matches = re.findall(pattern, cleaned)
            for key, value in matches:
                value = value.strip().strip('"')
                if not value or value.startswith('{{'):
                    continue
                # Try to convert to appropriate type
                val_lower = value.lower()
                if val_lower == 'true':
                    result[key] = True
                elif val_lower == 'false':
                    result[key] = False
                elif val_lower == 'null':
                    result[key] = None
                else:
                    try:
                        result[key] = float(value) if '.' in value else int(value)
                    except ValueError:
                        result[key] = value
            
            if result:
                logger.debug(f"Manual extraction found keys: {list(result.keys())}")
                return result
        except Exception as e:
            logger.debug(f"Manual JSON extraction failed: {e}")
        
        return None

    @staticmethod
    def _parse_json(data: dict) -> Dict:
        """
        Parse JSON-formatted alert.

        Supports multiple field name variations to accommodate different TradingView alert formats:
        - symbol / instrument / ticker
        - quantity / amount / contracts / order_contracts
        - action / side / order_action
        - Parses order_alert_message for embedded parameters
        """
        # Extract symbol (try multiple field names)
        symbol = ''
        for field in ['symbol', 'instrument', 'ticker']:
            val = data.get(field)
            if val and isinstance(val, str) and not val.startswith('{{'):
                symbol = val.upper()
                break

        # Extract action (try multiple field names, including TradingView strategy fields)
        action = ''
        for field in ['action', 'side', 'order_action']:
            val = data.get(field)
            if val and isinstance(val, str) and not val.startswith('{{'):
                action = val.lower()
                break

        # Extract quantity (try multiple field names, including TradingView strategy fields)
        quantity = 0
        for field in ['quantity', 'amount', 'contracts', 'order_contracts']:
            val = data.get(field)
            if val:
                try:
                    quantity = float(val)
                    if quantity > 0:
                        break
                except (ValueError, TypeError):
                    continue

        # Extract order_type (support multiple field name variations)
        order_type_raw = (
            data.get('order_type') or
            data.get('orderType') or
            data.get('investmentType') or
            data.get('investment_type') or
            'market'
        ).lower()

        # Map common order type aliases
        order_type_map = {
            'base': 'market',
            'mkt': 'market',
            'lmt': 'limit',
            'stp': 'stop',
        }
        order_type = order_type_map.get(order_type_raw, order_type_raw)

        # Parse order_alert_message if present (contains embedded JSON parameters)
        alert_message_params = {}
        raw_alert_message = data.get('order_alert_message', '')
        if raw_alert_message:
            alert_message_params = TradingViewAlertParser._parse_alert_message(raw_alert_message)

        # Extract leverage from alert_message_params or top-level
        leverage = None
        if 'leverage' in alert_message_params:
            try:
                leverage = float(alert_message_params['leverage'])
            except (ValueError, TypeError):
                pass
        elif 'leverage' in data:
            try:
                leverage = float(data['leverage'])
            except (ValueError, TypeError):
                pass

        # Extract stop_loss_price from alert_message_params or TradeAlgo fields
        stop_loss = None
        for field in ['stop_loss_price', 'stop_loss', 'StopLoss', 'Long Stop Price', 'Short Stop Price']:
            val = alert_message_params.get(field) or data.get(field)
            if val:
                try:
                    stop_loss = float(val)
                    break
                except (ValueError, TypeError):
                    continue

        # Extract order_price (for limit orders) - include TradeAlgo entry_price fields
        price = None
        for field in ['order_price', 'price', 'entry_price', 'EntryPrice',
                      'Long Entry Price', 'Short Entry Price']:
            val = data.get(field)
            if val:
                try:
                    price = float(val)
                    break
                except (ValueError, TypeError):
                    continue

        # Extract take_profit safely
        take_profit = None
        if 'take_profit' in data:
            try:
                take_profit = float(data['take_profit'])
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid take_profit value '{data['take_profit']}': {e}")

        # Extract trailing_stop_pct safely
        trailing_stop_pct = None
        if 'trailing_stop_pct' in data:
            try:
                trailing_stop_pct = float(data['trailing_stop_pct'])
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid trailing_stop_pct value '{data['trailing_stop_pct']}': {e}")

        # ============================================================
        # INDICATOR FALLBACK LOGIC
        # When strategy placeholders aren't populated (indicators don't have access to {{strategy.*}}),
        # try to infer trade data from signal_type field or plot values.
        # ============================================================
        
        # First check for explicit signal_type field (for indicator-based alerts)
        signal_type = str(data.get('signal_type', '') or alert_message_params.get('signal_type', '')).lower()
        
        if signal_type:
            logger.info(f"Found signal_type={signal_type} for {symbol}")
            
            # Map signal_type to action
            if signal_type in ['bull_entry', 'bull', 'long', 'buy']:
                action = 'buy'
                order_type = 'enter_long'
                logger.info(f"Mapped signal_type={signal_type} to buy/long entry")
            elif signal_type in ['bear_entry', 'bear', 'short', 'sell']:
                action = 'sell'
                order_type = 'enter_short'
                logger.info(f"Mapped signal_type={signal_type} to sell/short entry")
            elif signal_type in ['tp1', 'tp2', 'tp3', 'tp4', 'tp5']:
                # For TP signals, infer action from existing position (opposite of entry)
                # Default to buy (closing a short) - will be refined by trade grouping
                action = 'buy'
                order_type = 'reduce'
                logger.info(f"Mapped signal_type={signal_type} to take profit")
            elif signal_type in ['stop_loss', 'sl', 'stoploss']:
                action = 'buy'  # Default, will be refined
                order_type = 'exit'
                logger.info(f"Mapped signal_type={signal_type} to stop loss")
            elif signal_type in ['exit', 'close', 'flat']:
                action = 'buy'  # Default, will be refined
                order_type = 'exit'
                logger.info(f"Mapped signal_type={signal_type} to exit")
        
        # Extract plot values for indicator-based alerts
        plot_values = {}
        for key, value in data.items():
            if key.startswith('plot_') and len(key) > 5:
                try:
                    plot_values[key] = float(value) if value and not str(value).startswith('{{') else None
                except (ValueError, TypeError):
                    pass
        
        # Check if this looks like an unpopulated indicator alert (and no signal_type)
        is_indicator_alert = (not action or action.startswith('{{')) and symbol and plot_values
        
        if is_indicator_alert:
            logger.info(f"Detected indicator-based alert for {symbol}, attempting to infer trade data from plots")
            
            # Try to infer action from plot_0 (common pattern: 1=long, -1=short, 0=flat)
            plot_0 = plot_values.get('plot_0')
            if plot_0 is not None:
                if plot_0 == 1 or plot_0 == 1.0:
                    action = 'buy'
                    logger.info(f"Inferred action=buy from plot_0={plot_0}")
                elif plot_0 == -1 or plot_0 == -1.0:
                    action = 'sell'
                    logger.info(f"Inferred action=sell from plot_0={plot_0}")
            
            # Try to use plot_1 as price if not set
            plot_1 = plot_values.get('plot_1')
            if plot_1 is not None and price is None:
                price = plot_1
                logger.info(f"Using plot_1={plot_1} as price")
            
            # Fallback to close price if still no price
            if price is None:
                try:
                    close_val = data.get('close')
                    if close_val and not str(close_val).startswith('{{'):
                        price = float(close_val)
                        logger.info(f"Using close={price} as price")
                except (ValueError, TypeError):
                    pass
            
            # Try to use plot_2 as take_profit if available
            plot_2 = plot_values.get('plot_2')
            if plot_2 is not None and take_profit is None:
                take_profit = plot_2
                logger.info(f"Using plot_2={plot_2} as take_profit")
            
            # Try to use plot_3 as stop_loss if available
            plot_3 = plot_values.get('plot_3')
            if plot_3 is not None and stop_loss is None:
                stop_loss = plot_3
                logger.info(f"Using plot_3={plot_3} as stop_loss")
            
            # Default quantity for indicators (user can configure this)
            if quantity <= 0:
                quantity = 1  # Default to 1 unit for indicators
                logger.info(f"Using default quantity=1 for indicator alert")

        # Extract multiple take profit levels for TradeAlgo Elite
        take_profit_levels = {}
        for i in range(1, 6):
            for field in [f'take_profit_{i}', f'TakeProfit{i}',
                          f'Long TP-{i} Price', f'Short TP-{i} Price']:
                val = data.get(field)
                if val:
                    try:
                        take_profit_levels[f'take_profit_{i}'] = float(val)
                        break
                    except (ValueError, TypeError):
                        continue

        # Use first TP as the primary take_profit if not set
        if take_profit is None and take_profit_levels.get('take_profit_1'):
            take_profit = take_profit_levels['take_profit_1']

        return {
            'symbol': symbol,
            'action': action,
            'order_type': order_type,
            'quantity': quantity,
            'price': price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'trailing_stop_pct': trailing_stop_pct,
            'leverage': leverage,
            'test_mode': bool(data.get('test_mode', False)),  # Enable test mode to skip actual trade execution
            'metadata': {  # Store additional TradingView data for debugging/logging
                'timestamp': data.get('timestamp'),
                'exchange': data.get('exchange'),
                'full_ticker': data.get('full_ticker'),
                'interval': data.get('interval'),
                'order_id': data.get('order_id'),
                'order_comment': data.get('order_comment'),
                'position_size': data.get('position_size'),
                'position_avg_price': data.get('position_avg_price'),
                'market_position': data.get('market_position'),
                'raw_alert_message': raw_alert_message,
                'alert_message_params': alert_message_params,  # Store parsed parameters
                # TradeAlgo Elite fields
                'take_profit_levels': take_profit_levels,
                'tp_count': data.get('tp_count') or data.get('tpCount'),
                'atr_value': data.get('atr_value') or data.get('AtrValue'),
                'sl_dist_pips': data.get('sl_dist_pips') or data.get('slDistInPips'),
                'signal_type': data.get('signal_type')
            }
        }

    @staticmethod
    def _parse_alert_message(alert_message: str) -> Dict:
        """
        Parse the order_alert_message field which contains embedded JSON parameters.

        The alert_message often contains a JSON-like string with additional parameters
        like leverage, order_type (enter_long, reduce_long), position, etc.

        Args:
            alert_message: The raw alert message string

        Returns:
            dict: Parsed parameters from the alert message
        """
        if not alert_message or not isinstance(alert_message, str):
            return {}

        try:
            # Try parsing as-is first (in case it's valid JSON)
            return json.loads(alert_message)
        except json.JSONDecodeError:
            pass

        # Handle malformed JSON: sometimes starts with extra quote or missing braces
        cleaned = alert_message.strip()

        # Remove leading/trailing quotes if present
        if cleaned.startswith('"') and not cleaned.startswith('"{'):
            cleaned = cleaned[1:]

        # Handle double quotes at start (e.g., ""margin_mode" -> "margin_mode")
        while cleaned.startswith('""'):
            cleaned = cleaned[1:]

        # Clean up trailing junk: ," or , or trailing whitespace
        # But be careful not to strip valid JSON ending like "value"
        while cleaned.endswith(',"') or cleaned.endswith(','):
            if cleaned.endswith(',"'):
                cleaned = cleaned[:-2]
            elif cleaned.endswith(','):
                cleaned = cleaned[:-1]
        cleaned = cleaned.rstrip(' \t\n\r')

        # Handle case where string starts with "key": (missing opening brace)
        if re.match(r'^"[^"]+"\s*:', cleaned):
            cleaned = '{' + cleaned

        # Add braces if missing
        if not cleaned.startswith('{'):
            cleaned = '{' + cleaned
        if not cleaned.endswith('}'):
            cleaned = cleaned + '}'

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
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
    def _parse_text(text: str) -> Dict:
        """
        Parse custom text-formatted alert.

        Supported formats:
            "BUY BTCUSDT QTY:0.01"
            "SELL ETHUSDT QTY:0.5 PRICE:2000"
            "order buy @ 0.5 filled on BTCUSDT"  (strategy format)
            "buy BTCUSDT QTY:0.001"
        """
        text_upper = text.upper().strip()
        text_lower = text.lower().strip()

        # Try multiple extraction patterns
        action = None
        symbol = None
        quantity = None

        # Pattern 1: "BUY/SELL SYMBOL QTY:..." format
        match1 = re.search(r'\b(BUY|SELL)\s+([A-Z0-9\-_/.]+)\s+QTY[:\s]+([0-9.]+)', text_upper)
        if match1:
            action = match1.group(1).lower()
            symbol = match1.group(2)
            quantity = float(match1.group(3))

        # Pattern 2: Strategy format "order buy @ 0.5 filled on BTCUSDT"
        if not action:
            match2 = re.search(r'order\s+(buy|sell)\s+@\s+([0-9.]+)\s+(?:filled\s+)?on\s+([A-Z0-9\-_/.]+)', text_lower, re.IGNORECASE)
            if match2:
                action = match2.group(1).lower()
                quantity = float(match2.group(2))
                symbol = match2.group(3).upper()

        # Pattern 3: Simple "buy/sell SYMBOL QTY:..." (lowercase)
        if not action:
            match3 = re.search(r'\b(buy|sell)\s+([A-Z0-9\-_/.]+)\s+QTY[:\s]+([0-9.]+)', text_lower, re.IGNORECASE)
            if match3:
                action = match3.group(1).lower()
                symbol = match3.group(2).upper()
                quantity = float(match3.group(3))

        # Pattern 4: Just "BUY SYMBOL" without QTY (extract symbol, quantity must be in message)
        if not action:
            match4 = re.search(r'\b(BUY|SELL)\s+([A-Z0-9\-_/.]+)', text_upper)
            if match4:
                action = match4.group(1).lower()
                symbol = match4.group(2)
                # Try to find any number as quantity
                qty_match = re.search(r'([0-9.]+)', text)
                if qty_match:
                    quantity = float(qty_match.group(1))

        if not action:
            raise ValueError("Invalid alert: missing BUY or SELL action")
        if not symbol:
            raise ValueError("Invalid alert: missing trading symbol")
        if not quantity or quantity <= 0:
            raise ValueError("Invalid alert: missing or invalid quantity")

        # Extract optional parameters (works with all formats)
        price_match = re.search(r'PRICE[:\s]+([0-9.]+)', text_upper)
        sl_match = re.search(r'(?:SL|STOP[_\s]?LOSS)[:\s]+([0-9.]+)', text_upper)
        tp_match = re.search(r'(?:TP|TAKE[_\s]?PROFIT)[:\s]+([0-9.]+)', text_upper)
        trailing_match = re.search(r'TRAILING[:\s]+([0-9.]+)', text_upper)

        # Determine order type
        order_type = 'market'
        if trailing_match:
            order_type = 'trailing'
        elif price_match:
            order_type = 'limit'

        return {
            'symbol': symbol,
            'action': action,
            'order_type': order_type,
            'quantity': quantity,
            'price': float(price_match.group(1)) if price_match else None,
            'stop_loss': float(sl_match.group(1)) if sl_match else None,
            'take_profit': float(tp_match.group(1)) if tp_match else None,
            'trailing_stop_pct': float(trailing_match.group(1)) if trailing_match else None,
            'test_mode': False,  # Text format doesn't support test mode
            'metadata': {}  # Text format doesn't have additional metadata
        }

    @staticmethod
    def validate_params(params: Dict) -> Tuple[bool, Optional[str]]:
        """
        Validate parsed parameters.

        Returns:
            tuple: (is_valid: bool, error_message: Optional[str])
        """
        issues = []

        if not params.get('symbol'):
            issues.append("Missing or empty 'symbol' field")

        if params.get('action') not in ['buy', 'sell']:
            issues.append(f"Invalid or missing 'action': got '{params.get('action')}' (expected 'buy' or 'sell')")

        if not params.get('quantity') or params['quantity'] <= 0:
            issues.append(f"Invalid or missing 'quantity': got '{params.get('quantity')}' (must be > 0)")

        if params.get('order_type') == 'limit' and not params.get('price'):
            issues.append("Limit orders require a 'price'")

        if params.get('order_type') == 'trailing' and not params.get('trailing_stop_pct'):
            issues.append("Trailing stop orders require 'trailing_stop_pct'")

        if issues:
            # Provide detailed feedback about what fields were found
            metadata = params.get('metadata', {})
            found_fields = [k for k, v in params.items() if v and k != 'metadata']
            if metadata:
                found_fields.extend([f"metadata.{k}" for k in metadata.keys() if metadata.get(k)])

            error_msg = "; ".join(issues)
            if found_fields:
                error_msg += f" | Found fields: {', '.join(found_fields)}"

            return False, error_msg

        return True, None
