"""TradingView webhook alert parsing service."""
import json
import re
from typing import Dict, Optional, Tuple


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
            return TradingViewAlertParser._parse_json(data)
        except (json.JSONDecodeError, ValueError):
            pass

        # Fall back to text parsing
        return TradingViewAlertParser._parse_text(raw_message)

    @staticmethod
    def _parse_json(data: dict) -> Dict:
        """
        Parse JSON-formatted alert.

        Supports multiple field name variations to accommodate different TradingView alert formats:
        - symbol / instrument / ticker
        - quantity / amount / contracts
        - action / strategy.order.action
        """
        # Extract symbol (try multiple field names)
        symbol = (
            data.get('symbol') or
            data.get('instrument') or
            data.get('ticker') or
            ''
        ).upper()

        # Extract action (try multiple field names)
        action = (
            data.get('action') or
            data.get('side') or
            ''
        ).lower()

        # Extract quantity (try multiple field names)
        quantity_raw = (
            data.get('quantity') or
            data.get('amount') or
            data.get('contracts') or
            0
        )
        quantity = float(quantity_raw) if quantity_raw else 0

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

        return {
            'symbol': symbol,
            'action': action,
            'order_type': order_type,
            'quantity': quantity,
            'price': float(data['price']) if 'price' in data else None,
            'stop_loss': float(data['stop_loss']) if 'stop_loss' in data else None,
            'take_profit': float(data['take_profit']) if 'take_profit' in data else None,
            'trailing_stop_pct': float(data['trailing_stop_pct']) if 'trailing_stop_pct' in data else None,
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
                'market_position': data.get('market_position')
            }
        }

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
        if not params.get('symbol'):
            return False, "Missing trading symbol"

        if params.get('action') not in ['buy', 'sell']:
            return False, f"Invalid action: {params.get('action')}"

        if not params.get('quantity') or params['quantity'] <= 0:
            return False, "Invalid quantity: must be greater than 0"

        if params.get('order_type') == 'limit' and not params.get('price'):
            return False, "Limit orders require a price"

        if params.get('order_type') == 'trailing' and not params.get('trailing_stop_pct'):
            return False, "Trailing stop orders require trailing_stop_pct"

        return True, None
