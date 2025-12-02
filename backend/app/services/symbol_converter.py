"""Symbol format conversion for different brokers."""


class SymbolConverter:
    """Convert trading symbols between different broker formats."""

    @staticmethod
    def normalize_symbol(symbol: str, broker: str) -> str:
        """
        Convert symbol to broker-specific format.

        Args:
            symbol: Raw symbol (BTCUSDT, EURUSD, BTC-USDT, EUR_USD, etc.)
            broker: Target broker ('blofin' or 'oanda')

        Returns:
            str: Broker-specific format (BTC-USDT for Blofin, EUR_USD for Oanda)
        """
        # Remove common separators
        clean_symbol = symbol.replace('-', '').replace('_', '').replace('/', '').upper()

        if broker == 'blofin':
            # Blofin uses hyphen: BTC-USDT, ETH-USDT
            # Detect crypto pairs (ends with USDT, USDC, BTC, ETH)
            for quote in ['USDT', 'USDC', 'BTC', 'ETH']:
                if clean_symbol.endswith(quote):
                    base = clean_symbol[:-len(quote)]
                    return f"{base}-{quote}"
            # If no match, try to split (assume 3-4 char base, rest is quote)
            return f"{clean_symbol[:3]}-{clean_symbol[3:]}"

        elif broker == 'oanda':
            # Oanda uses underscore: EUR_USD, GBP_JPY
            # Most forex pairs are 6 characters (3+3)
            if len(clean_symbol) == 6:
                return f"{clean_symbol[:3]}_{clean_symbol[3:]}"
            # Handle longer symbols (e.g., XAUUSD = XAU_USD for gold)
            elif len(clean_symbol) == 7:
                return f"{clean_symbol[:4]}_{clean_symbol[4:]}"
            else:
                # Default: split in middle
                mid = len(clean_symbol) // 2
                return f"{clean_symbol[:mid]}_{clean_symbol[mid:]}"

        # Unknown broker, return as-is
        return symbol

    @staticmethod
    def detect_broker_from_symbol(symbol: str) -> str:
        """
        Auto-detect broker based on symbol format.

        Args:
            symbol: Trading symbol

        Returns:
            str: 'blofin' or 'oanda' or 'unknown'
        """
        clean = symbol.replace('-', '').replace('_', '').upper()

        # Crypto indicators
        crypto_suffixes = ['USDT', 'USDC', 'BTC', 'ETH', 'BNB']
        for suffix in crypto_suffixes:
            if clean.endswith(suffix):
                return 'blofin'

        # Forex indicators (common fiat currencies)
        forex_currencies = ['USD', 'EUR', 'GBP', 'JPY', 'CHF', 'AUD', 'CAD', 'NZD']
        if len(clean) == 6:
            base = clean[:3]
            quote = clean[3:]
            if base in forex_currencies and quote in forex_currencies:
                return 'oanda'

        return 'unknown'
