"""Blofin API client for executing crypto trades."""
import time
import hmac
import hashlib
import base64
import json
import requests
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class BlofinClient:
    """Client for interacting with Blofin API."""

    BASE_URL = "https://openapi.blofin.com"

    def __init__(self, api_key: str, secret_key: str, passphrase: str):
        """
        Initialize Blofin client.

        Args:
            api_key: Blofin API key
            secret_key: Blofin secret key
            passphrase: Blofin passphrase
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase

    def _generate_signature(self, timestamp: str, method: str, request_path: str, body: str = "") -> str:
        """
        Generate HMAC SHA256 signature for Blofin API.

        Args:
            timestamp: ISO timestamp
            method: HTTP method (GET, POST, etc.)
            request_path: API endpoint path
            body: Request body (empty string for GET)

        Returns:
            Base64-encoded signature
        """
        message = timestamp + method.upper() + request_path + body
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        )
        return base64.b64encode(signature.digest()).decode('utf-8')

    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """
        Make authenticated request to Blofin API.

        Args:
            method: HTTP method
            endpoint: API endpoint path (e.g., '/api/v1/trade/order')
            data: Request payload

        Returns:
            API response as dict
        """
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
        request_path = endpoint

        # Prepare body
        body = ""
        if data:
            body = json.dumps(data)

        # Generate signature
        signature = self._generate_signature(timestamp, method, request_path, body)

        # Build headers
        headers = {
            "ACCESS-KEY": self.api_key,
            "ACCESS-SIGN": signature,
            "ACCESS-TIMESTAMP": timestamp,
            "ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json"
        }

        # Make request
        url = self.BASE_URL + request_path
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, timeout=10)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, data=body, timeout=10)
            else:
                raise ValueError(f"Unsupported method: {method}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Blofin API request failed: {e}")
            return {"code": "error", "msg": str(e)}

    def place_market_order(
        self,
        symbol: str,
        side: str,
        size: float,
        client_order_id: Optional[str] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> Dict:
        """
        Place market order on Blofin.

        Args:
            symbol: Trading pair (e.g., 'BTC-USDT')
            side: 'buy' or 'sell'
            size: Order size in base currency
            client_order_id: Custom order ID
            stop_loss: Stop loss price (optional)
            take_profit: Take profit price (optional)

        Returns:
            API response
        """
        payload = {
            "instId": symbol,
            "tdMode": "cash",  # Cash/spot trading
            "side": side.lower(),
            "ordType": "market",
            "sz": str(size)
        }

        if client_order_id:
            payload["clOrdId"] = client_order_id

        # Note: Blofin doesn't support SL/TP in the same order for spot trading
        # They need to be placed as separate orders after the main order fills
        # For now, we'll log a warning if SL/TP are provided

        if stop_loss or take_profit:
            logger.warning("Stop loss and take profit must be set as separate orders on Blofin")

        logger.info(f"Placing Blofin market order: {side} {size} {symbol}")
        result = self._make_request("POST", "/api/v1/trade/order", payload)

        # If successful and SL/TP requested, place them as separate orders
        if result.get('code') == '0' and (stop_loss or take_profit):
            logger.info("Main order placed successfully, placing SL/TP orders...")
            # TODO: Implement separate SL/TP order placement
            # This would require getting the filled price and placing conditional orders

        return result

    def place_limit_order(
        self,
        symbol: str,
        side: str,
        size: float,
        price: float,
        client_order_id: Optional[str] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> Dict:
        """
        Place limit order on Blofin.

        Args:
            symbol: Trading pair (e.g., 'BTC-USDT')
            side: 'buy' or 'sell'
            size: Order size in base currency
            price: Limit price
            client_order_id: Custom order ID
            stop_loss: Stop loss price (optional)
            take_profit: Take profit price (optional)

        Returns:
            API response
        """
        payload = {
            "instId": symbol,
            "tdMode": "cash",
            "side": side.lower(),
            "ordType": "limit",
            "sz": str(size),
            "px": str(price)
        }

        if client_order_id:
            payload["clOrdId"] = client_order_id

        if stop_loss or take_profit:
            logger.warning("Stop loss and take profit must be set as separate orders on Blofin")

        logger.info(f"Placing Blofin limit order: {side} {size} {symbol} @ {price}")
        return self._make_request("POST", "/api/v1/trade/order", payload)

    def get_account_balance(self) -> Dict:
        """
        Get account balance.

        Returns:
            API response with balance information
        """
        return self._make_request("GET", "/api/v1/asset/balances")

    def get_order_details(self, order_id: str, symbol: str) -> Dict:
        """
        Get order details.

        Args:
            order_id: Order ID
            symbol: Trading pair

        Returns:
            API response with order details
        """
        endpoint = f"/api/v1/trade/order?ordId={order_id}&instId={symbol}"
        return self._make_request("GET", endpoint)
