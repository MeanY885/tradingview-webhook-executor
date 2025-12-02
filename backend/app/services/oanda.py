"""Oanda API client for executing forex trades."""
import requests
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class OandaClient:
    """Client for interacting with Oanda v20 API."""

    # Use practice environment by default, switch to live for production
    BASE_URL_PRACTICE = "https://api-fxpractice.oanda.com"
    BASE_URL_LIVE = "https://api-fxtrade.oanda.com"

    def __init__(self, api_key: str, account_id: str, is_live: bool = False):
        """
        Initialize Oanda client.

        Args:
            api_key: Oanda API token (Personal Access Token)
            account_id: Oanda account ID
            is_live: Use live environment (default: False for practice)
        """
        self.api_key = api_key
        self.account_id = account_id
        self.base_url = self.BASE_URL_LIVE if is_live else self.BASE_URL_PRACTICE

    def _get_headers(self) -> Dict[str, str]:
        """Get authentication headers for Oanda API."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """
        Make authenticated request to Oanda API.

        Args:
            method: HTTP method
            endpoint: API endpoint path
            data: Request payload

        Returns:
            API response as dict
        """
        url = self.base_url + endpoint
        headers = self._get_headers()

        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, timeout=10)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, json=data, timeout=10)
            else:
                raise ValueError(f"Unsupported method: {method}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Oanda API request failed: {e}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")
            return {"error": str(e)}

    def place_market_order(
        self,
        instrument: str,
        units: int,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        client_extensions: Optional[Dict] = None
    ) -> Dict:
        """
        Place market order on Oanda.

        Args:
            instrument: Currency pair (e.g., 'EUR_USD')
            units: Number of units (positive for buy, negative for sell)
            stop_loss: Stop loss price (optional)
            take_profit: Take profit price (optional)
            client_extensions: Custom order metadata

        Returns:
            API response
        """
        order_data = {
            "order": {
                "type": "MARKET",
                "instrument": instrument,
                "units": str(units),
                "timeInForce": "FOK",  # Fill or Kill
                "positionFill": "DEFAULT"
            }
        }

        # Add stop loss if provided
        if stop_loss is not None:
            order_data["order"]["stopLossOnFill"] = {
                "price": str(stop_loss)
            }

        # Add take profit if provided
        if take_profit is not None:
            order_data["order"]["takeProfitOnFill"] = {
                "price": str(take_profit)
            }

        # Add client extensions if provided
        if client_extensions:
            order_data["order"]["clientExtensions"] = client_extensions

        logger.info(f"Placing Oanda market order: {units} units of {instrument}")
        endpoint = f"/v3/accounts/{self.account_id}/orders"
        return self._make_request("POST", endpoint, order_data)

    def place_limit_order(
        self,
        instrument: str,
        units: int,
        price: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        client_extensions: Optional[Dict] = None
    ) -> Dict:
        """
        Place limit order on Oanda.

        Args:
            instrument: Currency pair (e.g., 'EUR_USD')
            units: Number of units (positive for buy, negative for sell)
            price: Limit price
            stop_loss: Stop loss price (optional)
            take_profit: Take profit price (optional)
            client_extensions: Custom order metadata

        Returns:
            API response
        """
        order_data = {
            "order": {
                "type": "LIMIT",
                "instrument": instrument,
                "units": str(units),
                "price": str(price),
                "timeInForce": "GTC",  # Good Till Cancelled
                "positionFill": "DEFAULT"
            }
        }

        # Add stop loss if provided
        if stop_loss is not None:
            order_data["order"]["stopLossOnFill"] = {
                "price": str(stop_loss)
            }

        # Add take profit if provided
        if take_profit is not None:
            order_data["order"]["takeProfitOnFill"] = {
                "price": str(take_profit)
            }

        # Add client extensions if provided
        if client_extensions:
            order_data["order"]["clientExtensions"] = client_extensions

        logger.info(f"Placing Oanda limit order: {units} units of {instrument} @ {price}")
        endpoint = f"/v3/accounts/{self.account_id}/orders"
        return self._make_request("POST", endpoint, order_data)

    def place_stop_order(
        self,
        instrument: str,
        units: int,
        price: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        client_extensions: Optional[Dict] = None
    ) -> Dict:
        """
        Place stop order on Oanda.

        Args:
            instrument: Currency pair (e.g., 'EUR_USD')
            units: Number of units (positive for buy, negative for sell)
            price: Stop price
            stop_loss: Stop loss price (optional)
            take_profit: Take profit price (optional)
            client_extensions: Custom order metadata

        Returns:
            API response
        """
        order_data = {
            "order": {
                "type": "STOP",
                "instrument": instrument,
                "units": str(units),
                "price": str(price),
                "timeInForce": "GTC",
                "positionFill": "DEFAULT"
            }
        }

        if stop_loss is not None:
            order_data["order"]["stopLossOnFill"] = {
                "price": str(stop_loss)
            }

        if take_profit is not None:
            order_data["order"]["takeProfitOnFill"] = {
                "price": str(take_profit)
            }

        if client_extensions:
            order_data["order"]["clientExtensions"] = client_extensions

        logger.info(f"Placing Oanda stop order: {units} units of {instrument} @ {price}")
        endpoint = f"/v3/accounts/{self.account_id}/orders"
        return self._make_request("POST", endpoint, order_data)

    def get_account_summary(self) -> Dict:
        """
        Get account summary.

        Returns:
            API response with account information
        """
        endpoint = f"/v3/accounts/{self.account_id}/summary"
        return self._make_request("GET", endpoint)

    def get_positions(self) -> Dict:
        """
        Get open positions.

        Returns:
            API response with positions
        """
        endpoint = f"/v3/accounts/{self.account_id}/positions"
        return self._make_request("GET", endpoint)

    def get_order_details(self, order_id: str) -> Dict:
        """
        Get order details.

        Args:
            order_id: Order ID

        Returns:
            API response with order details
        """
        endpoint = f"/v3/accounts/{self.account_id}/orders/{order_id}"
        return self._make_request("GET", endpoint)

    def close_position(self, instrument: str, units: Optional[str] = "ALL") -> Dict:
        """
        Close position for instrument.

        Args:
            instrument: Currency pair (e.g., 'EUR_USD')
            units: Number of units to close or "ALL" for entire position

        Returns:
            API response
        """
        # Determine if we're closing long or short position
        positions = self.get_positions()

        endpoint = f"/v3/accounts/{self.account_id}/positions/{instrument}/close"
        data = {}

        # Check for long position
        for pos in positions.get('positions', []):
            if pos['instrument'] == instrument:
                if int(pos['long']['units']) > 0:
                    data['longUnits'] = units
                if int(pos['short']['units']) < 0:
                    data['shortUnits'] = units

        logger.info(f"Closing Oanda position: {instrument}")
        return self._make_request("PUT", endpoint, data)
