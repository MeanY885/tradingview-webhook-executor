"""Signal parsers for different alert sources.

This module provides specialized parsers for different TradingView alert formats:
- OandaIndicatorParser: For Oanda forex indicator alerts with signal_type field
- Generic parser: For standard TradingView strategy alerts
"""
from .oanda_indicator import OandaIndicatorParser

__all__ = ['OandaIndicatorParser']
