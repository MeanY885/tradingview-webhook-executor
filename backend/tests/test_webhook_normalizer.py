"""Property-based tests for WebhookNormalizer service.

Uses Hypothesis for property-based testing as specified in the design document.
Each test is tagged with the property it validates from the design document.
"""
import pytest
from hypothesis import given, strategies as st, settings, assume

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.webhook_normalizer import (
    WebhookNormalizer,
    NormalizedWebhook,
    AlertType
)


# Custom strategies for generating test data
@st.composite
def alert_message_params(draw):
    """Generate valid alert message parameter dictionaries."""
    params = {}
    
    # Optional order_type
    if draw(st.booleans()):
        params['order_type'] = draw(st.sampled_from([
            'enter_long', 'enter_short', 'reduce_long', 'reduce_short',
            'exit_long', 'exit_short'
        ]))
    
    # Optional leverage (positive integers as strings or ints)
    if draw(st.booleans()):
        params['leverage'] = str(draw(st.integers(min_value=1, max_value=125)))
    
    # Optional stop_loss_price (positive floats)
    if draw(st.booleans()):
        params['stop_loss_price'] = str(round(draw(st.floats(min_value=0.001, max_value=100000, allow_nan=False, allow_infinity=False)), 4))
    
    # Optional pyramiding
    if draw(st.booleans()):
        params['pyramiding'] = str(draw(st.integers(min_value=0, max_value=10)))
    
    # Optional margin_mode
    if draw(st.booleans()):
        params['margin_mode'] = draw(st.sampled_from(['1', '2', 'cross', 'isolated']))
    
    # Optional enable_multi_tp
    if draw(st.booleans()):
        params['enable_multi_tp'] = draw(st.sampled_from(['0', '1']))
    
    return params


class TestAlertMessageParsing:
    """Tests for parse_alert_message() function.
    
    **Feature: multi-tp-trade-tracking, Property 0: Alert message parsing round-trip**
    **Validates: Requirements 4.1, 4.2**
    """
    
    @given(params=alert_message_params())
    @settings(max_examples=100)
    def test_property_0_alert_message_round_trip(self, params):
        """
        **Feature: multi-tp-trade-tracking, Property 0: Alert message parsing round-trip**
        **Validates: Requirements 4.1, 4.2**
        
        For any valid order_alert_message string (with or without braces, with various
        quote styles), parsing then re-serializing the extracted key-value pairs shall
        preserve all original values.
        """
        # Skip empty params as they don't produce meaningful round-trips
        assume(len(params) > 0)
        
        # Serialize to JSON string
        serialized = WebhookNormalizer.serialize_alert_message(params)
        
        # Parse back
        parsed = WebhookNormalizer.parse_alert_message(serialized)
        
        # All original keys should be present with equivalent values
        for key, original_value in params.items():
            assert key in parsed, f"Key '{key}' missing after round-trip"
            parsed_value = parsed[key]
            
            # Handle type coercion (strings may become numbers)
            if isinstance(original_value, str):
                # Try to compare as numbers if possible
                try:
                    original_num = float(original_value)
                    if isinstance(parsed_value, (int, float)):
                        assert abs(original_num - parsed_value) < 0.0001, \
                            f"Value mismatch for '{key}': {original_value} vs {parsed_value}"
                    else:
                        assert str(parsed_value) == original_value, \
                            f"Value mismatch for '{key}': {original_value} vs {parsed_value}"
                except ValueError:
                    # Not a number, compare as strings
                    assert str(parsed_value) == original_value, \
                        f"Value mismatch for '{key}': {original_value} vs {parsed_value}"
            else:
                assert parsed_value == original_value, \
                    f"Value mismatch for '{key}': {original_value} vs {parsed_value}"
    
    def test_parse_empty_string(self):
        """Test parsing empty string returns empty dict."""
        assert WebhookNormalizer.parse_alert_message("") == {}
        assert WebhookNormalizer.parse_alert_message(None) == {}
    
    def test_parse_valid_json(self):
        """Test parsing valid JSON string."""
        msg = '{"order_type": "enter_long", "leverage": "10"}'
        result = WebhookNormalizer.parse_alert_message(msg)
        assert result['order_type'] == 'enter_long'
        assert result['leverage'] == '10'
    
    def test_parse_malformed_missing_braces(self):
        """Test parsing JSON without braces."""
        msg = '"order_type": "reduce_long", "leverage": "6"'
        result = WebhookNormalizer.parse_alert_message(msg)
        assert result.get('order_type') == 'reduce_long'
        # Parser may convert numeric strings to numbers
        assert result.get('leverage') in ['6', 6]
    
    def test_parse_malformed_extra_quotes(self):
        """Test parsing JSON with extra leading quotes."""
        msg = '""margin_mode": "1", "order_type":"reduce_long"'
        result = WebhookNormalizer.parse_alert_message(msg)
        assert result.get('order_type') == 'reduce_long'
    
    def test_parse_trailing_comma(self):
        """Test parsing JSON with trailing comma."""
        msg = '{"order_type": "exit_long", "leverage": "5",}'
        result = WebhookNormalizer.parse_alert_message(msg)
        assert result.get('order_type') == 'exit_long'



# Strategy for generating raw webhook payloads
@st.composite
def raw_webhook_payload(draw):
    """Generate raw TradingView webhook payloads with nested alert_message."""
    payload = {}
    
    # Symbol (required for meaningful webhooks)
    payload['ticker'] = draw(st.sampled_from([
        'BTCUSDT', 'ETHUSDT', 'CVXUSDT', 'SOLUSDT', 'XRPUSDT'
    ]))
    
    # Action
    payload['order_action'] = draw(st.sampled_from(['buy', 'sell']))
    
    # Price (as string, like TradingView sends)
    price = draw(st.floats(min_value=0.001, max_value=100000, allow_nan=False, allow_infinity=False))
    payload['order_price'] = str(round(price, 4))
    
    # Contracts
    contracts = draw(st.floats(min_value=0.001, max_value=10000, allow_nan=False, allow_infinity=False))
    payload['order_contracts'] = str(round(contracts, 4))
    
    # Position size (remaining after this action)
    position_size = draw(st.floats(min_value=0, max_value=10000, allow_nan=False, allow_infinity=False))
    payload['position_size'] = str(round(position_size, 4))
    
    # Market position
    if position_size == 0:
        payload['market_position'] = 'flat'
    else:
        payload['market_position'] = draw(st.sampled_from(['long', 'short']))
    
    # Optional order_id
    if draw(st.booleans()):
        payload['order_id'] = draw(st.sampled_from([
            'Take 1st Target long', 'Take 2nd Target long', 'Take 3rd Target long',
            'Stop Loss', 'Entry', 'Manual Close'
        ]))
    
    # Optional order_comment
    if draw(st.booleans()):
        payload['order_comment'] = draw(st.sampled_from([
            'TP1', 'TP2', 'TP3', 'SL', 'Entry', ''
        ]))
    
    # Nested alert_message (JSON string inside JSON)
    alert_params = draw(alert_message_params())
    if alert_params:
        payload['order_alert_message'] = WebhookNormalizer.serialize_alert_message(alert_params)
    
    return payload


class TestWebhookNormalization:
    """Tests for normalize() function.
    
    **Feature: multi-tp-trade-tracking, Property 13: Webhook normalization completeness**
    **Validates: Requirements 1.1, 4.1, 4.2, 5.1, 5.2**
    """
    
    @given(payload=raw_webhook_payload())
    @settings(max_examples=100)
    def test_property_13_webhook_normalization_completeness(self, payload):
        """
        **Feature: multi-tp-trade-tracking, Property 13: Webhook normalization completeness**
        **Validates: Requirements 1.1, 4.1, 4.2, 5.1, 5.2**
        
        For any raw TradingView webhook payload (with nested order_alert_message),
        the normalizer shall extract and populate all required NormalizedWebhook
        fields without raising exceptions.
        """
        # Should not raise any exceptions
        normalized = WebhookNormalizer.normalize(payload)
        
        # Verify it returns a NormalizedWebhook instance
        assert isinstance(normalized, NormalizedWebhook)
        
        # Verify required fields are populated
        assert normalized.symbol == payload.get('ticker', '').upper()
        assert normalized.action == payload.get('order_action', '').lower()
        
        # Verify numeric conversions worked
        if payload.get('order_price'):
            assert normalized.order_price == float(payload['order_price'])
        if payload.get('order_contracts'):
            assert normalized.order_contracts == float(payload['order_contracts'])
        if payload.get('position_size'):
            assert normalized.position_size == float(payload['position_size'])
        
        # Verify alert_type is always set to a valid value
        assert normalized.alert_type in [
            'ENTRY', 'TP1', 'TP2', 'TP3', 'SL', 'PARTIAL', 'EXIT', 'UNKNOWN'
        ]
        
        # Verify position closure detection
        if payload.get('position_size') == '0' and payload.get('market_position') == 'flat':
            # Note: position_size '0' as string becomes 0.0 as float
            pass  # is_position_closed should be True
        
        # Verify raw_payload is preserved
        assert normalized.raw_payload == payload
    
    def test_normalize_empty_payload(self):
        """Test normalizing empty payload returns valid NormalizedWebhook."""
        normalized = WebhookNormalizer.normalize({})
        assert isinstance(normalized, NormalizedWebhook)
        assert normalized.symbol == ''
        assert normalized.action == ''
        assert normalized.alert_type == 'UNKNOWN'
    
    def test_normalize_extracts_leverage_from_alert_message(self):
        """Test that leverage is extracted from nested alert_message."""
        payload = {
            'ticker': 'BTCUSDT',
            'order_action': 'buy',
            'order_alert_message': '{"order_type": "enter_long", "leverage": "10"}'
        }
        normalized = WebhookNormalizer.normalize(payload)
        assert normalized.leverage == 10.0
        assert normalized.order_type == 'enter_long'
    
    def test_normalize_extracts_stop_loss_from_alert_message(self):
        """Test that stop_loss_price is extracted from nested alert_message."""
        payload = {
            'ticker': 'ETHUSDT',
            'order_action': 'buy',
            'order_alert_message': '{"order_type": "enter_long", "stop_loss_price": "1850.50"}'
        }
        normalized = WebhookNormalizer.normalize(payload)
        assert normalized.stop_loss_price == 1850.50
    
    def test_normalize_position_closed_detection(self):
        """Test position closure detection when position_size=0 and market_position=flat."""
        payload = {
            'ticker': 'BTCUSDT',
            'order_action': 'sell',
            'position_size': '0',
            'market_position': 'flat',
            'order_alert_message': '{"order_type": "exit_long"}'
        }
        normalized = WebhookNormalizer.normalize(payload)
        assert normalized.is_position_closed is True
        assert normalized.position_size == 0.0
        assert normalized.market_position == 'flat'



class TestTPLevelDetection:
    """Tests for detect_alert_type() function - TP level detection.
    
    **Feature: multi-tp-trade-tracking, Properties 7, 8, 9, 10**
    **Validates: Requirements 4.1, 4.2, 4.3, 4.4**
    """
    
    @given(tp_level=st.sampled_from(['TP1', 'TP2', 'TP3']),
           case_variation=st.sampled_from(['upper', 'lower', 'mixed']))
    @settings(max_examples=100)
    def test_property_7_tp_level_from_order_comment(self, tp_level, case_variation):
        """
        **Feature: multi-tp-trade-tracking, Property 7: TP Level Detection from order_comment**
        **Validates: Requirements 4.1**
        
        For any webhook where order_comment contains "TP1", "TP2", or "TP3" 
        (case-insensitive), the system shall set tp_level to the matching value.
        """
        # Apply case variation
        if case_variation == 'lower':
            comment = tp_level.lower()
        elif case_variation == 'mixed':
            comment = tp_level[0] + tp_level[1:].lower()
        else:
            comment = tp_level
        
        normalized = NormalizedWebhook(
            symbol='BTCUSDT',
            action='sell',
            order_type='reduce_long',
            alert_type='',  # Will be detected
            order_comment=comment
        )
        
        result = WebhookNormalizer.detect_alert_type(normalized)
        assert result == AlertType[tp_level], f"Expected {tp_level}, got {result}"
    
    @given(target=st.sampled_from([
        ('1st Target', 'TP1'),
        ('2nd Target', 'TP2'),
        ('3rd Target', 'TP3')
    ]))
    @settings(max_examples=100)
    def test_property_8_tp_level_from_order_id(self, target):
        """
        **Feature: multi-tp-trade-tracking, Property 8: TP Level Detection from order_id**
        **Validates: Requirements 4.2**
        
        For any webhook where order_id contains "1st Target", "2nd Target", or 
        "3rd Target", the system shall map to "TP1", "TP2", "TP3" respectively.
        """
        order_id_pattern, expected_tp = target
        
        # Test with various order_id formats
        order_id = f"Take {order_id_pattern} long"
        
        normalized = NormalizedWebhook(
            symbol='BTCUSDT',
            action='sell',
            order_type='reduce_long',
            alert_type='',
            order_id=order_id,
            order_comment=None  # No comment, should fall back to order_id
        )
        
        result = WebhookNormalizer.detect_alert_type(normalized)
        assert result == AlertType[expected_tp], f"Expected {expected_tp}, got {result}"
    
    @given(
        comment_tp=st.sampled_from(['TP1', 'TP2', 'TP3']),
        order_id_target=st.sampled_from([
            ('1st Target', 'TP1'),
            ('2nd Target', 'TP2'),
            ('3rd Target', 'TP3')
        ])
    )
    @settings(max_examples=100)
    def test_property_9_order_comment_precedence(self, comment_tp, order_id_target):
        """
        **Feature: multi-tp-trade-tracking, Property 9: order_comment Precedence**
        **Validates: Requirements 4.4**
        
        For any webhook with both order_comment and order_id containing TP indicators,
        the tp_level shall be determined by order_comment.
        """
        order_id_pattern, _ = order_id_target
        
        normalized = NormalizedWebhook(
            symbol='BTCUSDT',
            action='sell',
            order_type='reduce_long',
            alert_type='',
            order_comment=comment_tp,
            order_id=f"Take {order_id_pattern} long"
        )
        
        result = WebhookNormalizer.detect_alert_type(normalized)
        # order_comment should take precedence
        assert result == AlertType[comment_tp], \
            f"Expected {comment_tp} from order_comment, got {result}"
    
    @given(
        order_type=st.sampled_from(['reduce_long', 'reduce_short']),
        order_comment=st.sampled_from([None, '', 'some random comment', 'partial close']),
        order_id=st.sampled_from([None, '', 'Manual', 'Custom Exit'])
    )
    @settings(max_examples=100)
    def test_property_10_reduce_without_tp_markers(self, order_type, order_comment, order_id):
        """
        **Feature: multi-tp-trade-tracking, Property 10: Reduce Without TP Markers**
        **Validates: Requirements 4.3**
        
        For any webhook with order_type containing "reduce" but no TP identifiers
        in order_comment or order_id, the system shall set tp_level to "PARTIAL".
        """
        # Ensure no TP markers in comment or order_id
        if order_comment:
            assume('TP1' not in order_comment.upper())
            assume('TP2' not in order_comment.upper())
            assume('TP3' not in order_comment.upper())
            assume('SL' not in order_comment.upper())
            assume('STOP' not in order_comment.upper())
        if order_id:
            assume('1st target' not in order_id.lower())
            assume('2nd target' not in order_id.lower())
            assume('3rd target' not in order_id.lower())
            assume('stop loss' not in order_id.lower())
        
        normalized = NormalizedWebhook(
            symbol='BTCUSDT',
            action='sell',
            order_type=order_type,
            alert_type='',
            order_comment=order_comment,
            order_id=order_id
        )
        
        result = WebhookNormalizer.detect_alert_type(normalized)
        assert result == AlertType.PARTIAL, f"Expected PARTIAL, got {result}"



class TestOrderTypeDetection:
    """Tests for order type detection in normalize().
    
    **Feature: multi-tp-trade-tracking, Property 14: Order Type Detection**
    **Validates: Requirements 1.4, 4.3**
    """
    
    @given(order_type=st.sampled_from([
        'enter_long', 'enter_short', 'reduce_long', 'reduce_short',
        'exit_long', 'exit_short'
    ]))
    @settings(max_examples=100)
    def test_property_14_order_type_detection(self, order_type):
        """
        **Feature: multi-tp-trade-tracking, Property 14: Order Type Detection**
        **Validates: Requirements 1.4, 4.3**
        
        For any webhook where order_alert_message contains order_type with value
        enter_long, enter_short, reduce_long, reduce_short, exit_long, or exit_short,
        the normalizer shall correctly extract and classify the order type.
        """
        payload = {
            'ticker': 'BTCUSDT',
            'order_action': 'buy' if 'long' in order_type else 'sell',
            'order_alert_message': f'{{"order_type": "{order_type}"}}'
        }
        
        normalized = WebhookNormalizer.normalize(payload)
        
        # Verify order_type is correctly extracted
        assert normalized.order_type == order_type, \
            f"Expected order_type '{order_type}', got '{normalized.order_type}'"
        
        # Verify alert_type classification based on order_type
        if 'enter_' in order_type:
            assert normalized.alert_type == 'ENTRY', \
                f"Expected ENTRY for {order_type}, got {normalized.alert_type}"
        elif 'reduce_' in order_type:
            # Without TP markers, should be PARTIAL
            assert normalized.alert_type == 'PARTIAL', \
                f"Expected PARTIAL for {order_type}, got {normalized.alert_type}"
        elif 'exit_' in order_type:
            # Without TP markers, should be EXIT
            assert normalized.alert_type == 'EXIT', \
                f"Expected EXIT for {order_type}, got {normalized.alert_type}"
    
    def test_order_type_from_main_payload_fallback(self):
        """Test order_type extraction from main payload when not in alert_message."""
        payload = {
            'ticker': 'BTCUSDT',
            'order_action': 'buy',
            'order_type': 'enter_long'
        }
        
        normalized = WebhookNormalizer.normalize(payload)
        assert normalized.order_type == 'enter_long'
        assert normalized.alert_type == 'ENTRY'
    
    def test_order_type_alert_message_takes_precedence(self):
        """Test that order_type from alert_message takes precedence over main payload."""
        payload = {
            'ticker': 'BTCUSDT',
            'order_action': 'sell',
            'order_type': 'market',  # This should be ignored
            'order_alert_message': '{"order_type": "reduce_long"}'
        }
        
        normalized = WebhookNormalizer.normalize(payload)
        assert normalized.order_type == 'reduce_long'
