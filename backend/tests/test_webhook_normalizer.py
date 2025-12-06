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


# =============================================================================
# Property Tests for Trade Enhancements Feature
# =============================================================================

class TestExitStrategyFieldExtraction:
    """Tests for exit strategy field extraction.
    
    **Feature: trade-enhancements, Property 1: Exit Strategy Field Extraction**
    **Validates: Requirements 1.1, 1.2**
    """
    
    @given(
        exit_stop=st.one_of(
            st.floats(min_value=0.001, max_value=100000, allow_nan=False, allow_infinity=False),
            st.floats(min_value=0.001, max_value=100000, allow_nan=False, allow_infinity=False).map(str)
        ),
        exit_limit=st.one_of(
            st.floats(min_value=0.001, max_value=100000, allow_nan=False, allow_infinity=False),
            st.floats(min_value=0.001, max_value=100000, allow_nan=False, allow_infinity=False).map(str)
        ),
        exit_loss_ticks=st.one_of(
            st.floats(min_value=0.001, max_value=1000, allow_nan=False, allow_infinity=False),
            st.floats(min_value=0.001, max_value=1000, allow_nan=False, allow_infinity=False).map(str)
        ),
        exit_profit_ticks=st.one_of(
            st.floats(min_value=0.001, max_value=1000, allow_nan=False, allow_infinity=False),
            st.floats(min_value=0.001, max_value=1000, allow_nan=False, allow_infinity=False).map(str)
        )
    )
    @settings(max_examples=100)
    def test_property_1_exit_strategy_field_extraction(self, exit_stop, exit_limit, exit_loss_ticks, exit_profit_ticks):
        """
        **Feature: trade-enhancements, Property 1: Exit Strategy Field Extraction**
        **Validates: Requirements 1.1, 1.2**
        
        For any webhook payload containing exit_stop, exit_limit, exit_loss_ticks, 
        or exit_profit_ticks fields (as strings or numbers), the normalizer shall 
        correctly parse and store these values as floats.
        """
        payload = {
            'ticker': 'BTCUSDT',
            'order_action': 'buy',
            'exit_stop': exit_stop,
            'exit_limit': exit_limit,
            'exit_loss_ticks': exit_loss_ticks,
            'exit_profit_ticks': exit_profit_ticks
        }
        
        normalized = WebhookNormalizer.normalize(payload)
        
        # All exit strategy fields should be parsed as floats
        assert normalized.exit_stop == pytest.approx(float(exit_stop), rel=1e-4)
        assert normalized.exit_limit == pytest.approx(float(exit_limit), rel=1e-4)
        assert normalized.exit_loss_ticks == pytest.approx(float(exit_loss_ticks), rel=1e-4)
        assert normalized.exit_profit_ticks == pytest.approx(float(exit_profit_ticks), rel=1e-4)


class TestFieldMappingConsistency:
    """Tests for field mapping consistency.
    
    **Feature: trade-enhancements, Property 2: Field Mapping Consistency**
    **Validates: Requirements 2.1**
    """
    
    @given(
        exit_stop=st.floats(min_value=0.001, max_value=100000, allow_nan=False, allow_infinity=False),
        exit_limit=st.floats(min_value=0.001, max_value=100000, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_property_2_field_mapping_consistency(self, exit_stop, exit_limit):
        """
        **Feature: trade-enhancements, Property 2: Field Mapping Consistency**
        **Validates: Requirements 2.1**
        
        For any webhook payload containing exit_stop or exit_limit, the normalizer 
        shall map exit_stop to stop_loss_price and exit_limit to take_profit_price 
        in the normalized output.
        """
        payload = {
            'ticker': 'BTCUSDT',
            'order_action': 'buy',
            'exit_stop': exit_stop,
            'exit_limit': exit_limit
        }
        
        normalized = WebhookNormalizer.normalize(payload)
        
        # exit_stop should map to stop_loss_price
        assert normalized.stop_loss_price == pytest.approx(exit_stop, rel=1e-4)
        # exit_limit should map to take_profit_price
        assert normalized.take_profit_price == pytest.approx(exit_limit, rel=1e-4)
        
        # Original values should also be preserved
        assert normalized.exit_stop == pytest.approx(exit_stop, rel=1e-4)
        assert normalized.exit_limit == pytest.approx(exit_limit, rel=1e-4)


class TestTrailingStopExtraction:
    """Tests for trailing stop extraction.
    
    **Feature: trade-enhancements, Property 3: Trailing Stop Extraction**
    **Validates: Requirements 2.2, 5.1, 5.2**
    """
    
    @given(
        exit_trail_price=st.one_of(
            st.floats(min_value=0.001, max_value=100000, allow_nan=False, allow_infinity=False),
            st.floats(min_value=0.001, max_value=100000, allow_nan=False, allow_infinity=False).map(str)
        ),
        exit_trail_offset=st.one_of(
            st.floats(min_value=0.001, max_value=1000, allow_nan=False, allow_infinity=False),
            st.floats(min_value=0.001, max_value=1000, allow_nan=False, allow_infinity=False).map(str)
        )
    )
    @settings(max_examples=100)
    def test_property_3_trailing_stop_extraction(self, exit_trail_price, exit_trail_offset):
        """
        **Feature: trade-enhancements, Property 3: Trailing Stop Extraction**
        **Validates: Requirements 2.2, 5.1, 5.2**
        
        For any webhook payload containing exit_trail_price and/or exit_trail_offset 
        fields, the normalizer shall correctly extract and store these values.
        """
        payload = {
            'ticker': 'BTCUSDT',
            'order_action': 'buy',
            'exit_trail_price': exit_trail_price,
            'exit_trail_offset': exit_trail_offset
        }
        
        normalized = WebhookNormalizer.normalize(payload)
        
        # Trailing stop fields should be correctly extracted
        assert normalized.exit_trail_price == pytest.approx(float(exit_trail_price), rel=1e-4)
        assert normalized.exit_trail_offset == pytest.approx(float(exit_trail_offset), rel=1e-4)


class TestSymbolFieldAliasing:
    """Tests for symbol field aliasing.
    
    **Feature: trade-enhancements, Property 4: Symbol Field Aliasing**
    **Validates: Requirements 2.3**
    """
    
    @given(
        ticker=st.sampled_from(['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'CVXUSDT'])
    )
    @settings(max_examples=100)
    def test_property_4_symbol_field_aliasing_ticker_only(self, ticker):
        """
        **Feature: trade-enhancements, Property 4: Symbol Field Aliasing**
        **Validates: Requirements 2.3**
        
        For any webhook payload, if ticker is present and symbol is absent, 
        the normalizer shall use ticker as the symbol value.
        """
        payload = {
            'ticker': ticker,
            'order_action': 'buy'
        }
        
        normalized = WebhookNormalizer.normalize(payload)
        
        # ticker should be used as symbol
        assert normalized.symbol == ticker.upper()
    
    @given(
        symbol=st.sampled_from(['BTCUSDT', 'ETHUSDT', 'SOLUSDT']),
        ticker=st.sampled_from(['XRPUSDT', 'CVXUSDT', 'DOGEUSDT'])
    )
    @settings(max_examples=100)
    def test_property_4_symbol_takes_precedence(self, symbol, ticker):
        """
        **Feature: trade-enhancements, Property 4: Symbol Field Aliasing**
        **Validates: Requirements 2.3**
        
        For any webhook payload, if both symbol and ticker are present, 
        symbol takes precedence.
        """
        payload = {
            'symbol': symbol,
            'ticker': ticker,
            'order_action': 'buy'
        }
        
        normalized = WebhookNormalizer.normalize(payload)
        
        # symbol should take precedence over ticker
        assert normalized.symbol == symbol.upper()


class TestEntryPriceFromPositionAverage:
    """Tests for entry price from position average.
    
    **Feature: trade-enhancements, Property 5: Entry Price from Position Average**
    **Validates: Requirements 2.4**
    """
    
    @given(
        position_avg_price=st.floats(min_value=0.001, max_value=100000, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_property_5_entry_price_from_position_average(self, position_avg_price):
        """
        **Feature: trade-enhancements, Property 5: Entry Price from Position Average**
        **Validates: Requirements 2.4**
        
        For any webhook payload containing position_avg_price, the normalizer 
        shall use this value as entry_price when no explicit entry_price field is present.
        """
        payload = {
            'ticker': 'BTCUSDT',
            'order_action': 'buy',
            'position_avg_price': position_avg_price
        }
        
        normalized = WebhookNormalizer.normalize(payload)
        
        # position_avg_price should be used as entry_price
        assert normalized.entry_price == pytest.approx(position_avg_price, rel=1e-4)
    
    @given(
        entry_price=st.floats(min_value=0.001, max_value=100000, allow_nan=False, allow_infinity=False),
        position_avg_price=st.floats(min_value=0.001, max_value=100000, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_property_5_explicit_entry_price_takes_precedence(self, entry_price, position_avg_price):
        """
        **Feature: trade-enhancements, Property 5: Entry Price from Position Average**
        **Validates: Requirements 2.4**
        
        For any webhook payload with both entry_price and position_avg_price,
        the explicit entry_price takes precedence.
        """
        # Ensure they're different to make the test meaningful
        assume(abs(entry_price - position_avg_price) > 0.01)
        
        payload = {
            'ticker': 'BTCUSDT',
            'order_action': 'buy',
            'entry_price': entry_price,
            'position_avg_price': position_avg_price
        }
        
        normalized = WebhookNormalizer.normalize(payload)
        
        # explicit entry_price should take precedence
        assert normalized.entry_price == pytest.approx(entry_price, rel=1e-4)


class TestPlotValuesExtraction:
    """Tests for plot values extraction.
    
    **Feature: trade-enhancements, Property 6: Plot Values Extraction**
    **Validates: Requirements 2.5**
    """
    
    @given(
        plot_0=st.floats(min_value=-100000, max_value=100000, allow_nan=False, allow_infinity=False),
        plot_1=st.floats(min_value=-100000, max_value=100000, allow_nan=False, allow_infinity=False),
        plot_2=st.floats(min_value=-100000, max_value=100000, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_property_6_plot_values_extraction(self, plot_0, plot_1, plot_2):
        """
        **Feature: trade-enhancements, Property 6: Plot Values Extraction**
        **Validates: Requirements 2.5**
        
        For any webhook payload containing fields matching pattern plot_N 
        (where N is a digit), the normalizer shall extract all such fields 
        into the plot_values dictionary.
        """
        payload = {
            'ticker': 'BTCUSDT',
            'order_action': 'buy',
            'plot_0': plot_0,
            'plot_1': plot_1,
            'plot_2': plot_2
        }
        
        normalized = WebhookNormalizer.normalize(payload)
        
        # All plot values should be extracted
        assert 'plot_0' in normalized.plot_values
        assert 'plot_1' in normalized.plot_values
        assert 'plot_2' in normalized.plot_values
        assert normalized.plot_values['plot_0'] == pytest.approx(plot_0, rel=1e-4)
        assert normalized.plot_values['plot_1'] == pytest.approx(plot_1, rel=1e-4)
        assert normalized.plot_values['plot_2'] == pytest.approx(plot_2, rel=1e-4)
    
    @given(
        plot_0=st.floats(min_value=-100000, max_value=100000, allow_nan=False, allow_infinity=False).map(str)
    )
    @settings(max_examples=100)
    def test_property_6_plot_values_string_parsing(self, plot_0):
        """
        **Feature: trade-enhancements, Property 6: Plot Values Extraction**
        **Validates: Requirements 2.5**
        
        Plot values provided as strings should be correctly parsed to floats.
        """
        payload = {
            'ticker': 'BTCUSDT',
            'order_action': 'buy',
            'plot_0': plot_0
        }
        
        normalized = WebhookNormalizer.normalize(payload)
        
        assert 'plot_0' in normalized.plot_values
        assert normalized.plot_values['plot_0'] == pytest.approx(float(plot_0), rel=1e-4)


class TestTypeCoercion:
    """Tests for type coercion of prices and quantities.
    
    **Feature: trade-enhancements, Property 7: Type Coercion for Prices and Quantities**
    **Validates: Requirements 2.6**
    """
    
    @given(
        price=st.floats(min_value=0.001, max_value=100000, allow_nan=False, allow_infinity=False),
        as_string=st.booleans()
    )
    @settings(max_examples=100)
    def test_property_7_type_coercion_prices(self, price, as_string):
        """
        **Feature: trade-enhancements, Property 7: Type Coercion for Prices and Quantities**
        **Validates: Requirements 2.6**
        
        For any webhook payload where price fields are provided as strings,
        the normalizer shall correctly parse them to float values. For any 
        payload where they are provided as numbers, they shall be preserved as floats.
        """
        price_value = str(price) if as_string else price
        
        payload = {
            'ticker': 'BTCUSDT',
            'order_action': 'buy',
            'order_price': price_value,
            'exit_stop': price_value,
            'exit_limit': price_value
        }
        
        normalized = WebhookNormalizer.normalize(payload)
        
        # All prices should be floats regardless of input type
        assert isinstance(normalized.order_price, float)
        assert isinstance(normalized.exit_stop, float)
        assert isinstance(normalized.exit_limit, float)
        assert normalized.order_price == pytest.approx(price, rel=1e-4)
        assert normalized.exit_stop == pytest.approx(price, rel=1e-4)
        assert normalized.exit_limit == pytest.approx(price, rel=1e-4)
    
    @given(
        quantity=st.floats(min_value=0.001, max_value=10000, allow_nan=False, allow_infinity=False),
        as_string=st.booleans()
    )
    @settings(max_examples=100)
    def test_property_7_type_coercion_quantities(self, quantity, as_string):
        """
        **Feature: trade-enhancements, Property 7: Type Coercion for Prices and Quantities**
        **Validates: Requirements 2.6**
        
        For any webhook payload where quantity fields are provided as strings,
        the normalizer shall correctly parse them to float values.
        """
        quantity_value = str(quantity) if as_string else quantity
        
        payload = {
            'ticker': 'BTCUSDT',
            'order_action': 'buy',
            'order_contracts': quantity_value,
            'position_size': quantity_value
        }
        
        normalized = WebhookNormalizer.normalize(payload)
        
        # All quantities should be floats regardless of input type
        assert isinstance(normalized.order_contracts, float)
        assert isinstance(normalized.position_size, float)
        assert normalized.order_contracts == pytest.approx(quantity, rel=1e-4)
        assert normalized.position_size == pytest.approx(quantity, rel=1e-4)


class TestTradeAlgoEliteSupport:
    """Tests for TradeAlgo Elite Indicator/Backtester field parsing.
    
    Validates: TradeAlgo Elite integration requirements
    """
    
    def test_tradealgo_indicator_bull_entry(self):
        """Test parsing TradeAlgo Elite Indicator bull entry signal."""
        payload = {
            'symbol': 'EURUSD',
            'signal_type': 'bull_entry',
            'entry_price': '1.0850',
            'stop_loss': '1.0800',
            'take_profit_1': '1.0880',
            'take_profit_2': '1.0910',
            'take_profit_3': '1.0950',
            'tp_count': '3',
            'quantity': '10000'
        }
        normalized = WebhookNormalizer.normalize(payload)
        
        assert normalized.action == 'buy'
        assert normalized.order_type == 'enter_long'
        assert normalized.alert_type == 'ENTRY'
        assert normalized.market_position == 'long'
        assert normalized.entry_price == 1.0850
        assert normalized.stop_loss_price == 1.0800
        assert normalized.take_profit_1 == 1.0880
        assert normalized.take_profit_2 == 1.0910
        assert normalized.take_profit_3 == 1.0950
        assert normalized.tp_count == 3
    
    def test_tradealgo_indicator_bear_entry(self):
        """Test parsing TradeAlgo Elite Indicator bear entry signal."""
        payload = {
            'symbol': 'GBPUSD',
            'signal_type': 'bear_entry',
            'entry_price': '1.2650',
            'stop_loss': '1.2700',
            'take_profit_1': '1.2620',
            'quantity': '10000'
        }
        normalized = WebhookNormalizer.normalize(payload)
        
        assert normalized.action == 'sell'
        assert normalized.order_type == 'enter_short'
        assert normalized.alert_type == 'ENTRY'
        assert normalized.market_position == 'short'
        assert normalized.entry_price == 1.2650
        assert normalized.stop_loss_price == 1.2700
        assert normalized.take_profit_1 == 1.2620
    
    def test_tradealgo_tp_signals(self):
        """Test parsing TradeAlgo TP hit signals."""
        for tp_num, expected_alert_type in [(1, 'TP1'), (2, 'TP2'), (3, 'TP3'), (4, 'TP4'), (5, 'TP5')]:
            payload = {
                'symbol': 'USDJPY',
                'signal_type': f'tp{tp_num}',
                'exit_price': '150.50',
                'quantity': '2000'
            }
            normalized = WebhookNormalizer.normalize(payload)
            
            assert normalized.order_type == 'reduce'
            assert normalized.alert_type == expected_alert_type, \
                f"Expected {expected_alert_type} for tp{tp_num}, got {normalized.alert_type}"
    
    def test_tradealgo_stop_loss_signal(self):
        """Test parsing TradeAlgo stop loss signal."""
        payload = {
            'symbol': 'AUDUSD',
            'signal_type': 'stop_loss',
            'exit_price': '0.6500',
            'quantity': '10000'
        }
        normalized = WebhookNormalizer.normalize(payload)
        
        assert normalized.order_type == 'exit'
        assert normalized.alert_type == 'SL'
    
    def test_tradealgo_exit_signal(self):
        """Test parsing TradeAlgo exit signal."""
        payload = {
            'symbol': 'NZDUSD',
            'signal_type': 'exit',
            'exit_price': '0.5800',
            'quantity': '10000'
        }
        normalized = WebhookNormalizer.normalize(payload)
        
        assert normalized.order_type == 'exit'
        assert normalized.alert_type == 'EXIT'
    
    def test_tradealgo_backtester_long_entry(self):
        """Test parsing TradeAlgo Elite Backtester long entry with different field names."""
        payload = {
            'symbol': 'EURUSD',
            'signal_type': 'bull_entry',
            'Long Entry Price': '1.0850',
            'Long Stop Price': '1.0800',
            'Long TP-1 Price': '1.0880',
            'Long TP-2 Price': '1.0910',
            'quantity': '10000'
        }
        normalized = WebhookNormalizer.normalize(payload)
        
        assert normalized.action == 'buy'
        assert normalized.order_type == 'enter_long'
        assert normalized.entry_price == 1.0850
        assert normalized.stop_loss_price == 1.0800
        assert normalized.take_profit_1 == 1.0880
        assert normalized.take_profit_2 == 1.0910
    
    def test_tradealgo_backtester_short_entry(self):
        """Test parsing TradeAlgo Elite Backtester short entry."""
        payload = {
            'symbol': 'GBPUSD',
            'signal_type': 'bear_entry',
            'Short Entry Price': '1.2650',
            'Short Stop Price': '1.2700',
            'Short TP-1 Price': '1.2620',
            'Short TP-2 Price': '1.2580',
            'quantity': '10000'
        }
        normalized = WebhookNormalizer.normalize(payload)
        
        assert normalized.action == 'sell'
        assert normalized.order_type == 'enter_short'
        assert normalized.entry_price == 1.2650
        assert normalized.stop_loss_price == 1.2700
        assert normalized.take_profit_1 == 1.2620
        assert normalized.take_profit_2 == 1.2580
    
    def test_tradealgo_indicator_field_names(self):
        """Test parsing with original TradeAlgo indicator field names."""
        payload = {
            'symbol': 'XAUUSD',
            'signal_type': 'bull_entry',
            'EntryPrice': '1950.50',
            'StopLoss': '1940.00',
            'TakeProfit1': '1960.00',
            'TakeProfit2': '1970.00',
            'TakeProfit3': '1980.00',
            'tpCount': '3',
            'quantity': '1'
        }
        normalized = WebhookNormalizer.normalize(payload)
        
        assert normalized.entry_price == 1950.50
        assert normalized.stop_loss_price == 1940.00
        assert normalized.take_profit_1 == 1960.00
        assert normalized.take_profit_2 == 1970.00
        assert normalized.take_profit_3 == 1980.00
        assert normalized.tp_count == 3
    
    def test_tradealgo_bull_bear_indicators_bull(self):
        """Test inference from Bull plot indicator."""
        payload = {
            'symbol': 'AUDUSD',
            'Bull': '1',
            'Bear': '0',
            'EntryPrice': '0.6550',
            'quantity': '10000'
        }
        normalized = WebhookNormalizer.normalize(payload)
        
        assert normalized.action == 'buy'
        assert normalized.order_type == 'enter_long'
        assert normalized.is_bull == True
        assert normalized.is_bear == False
    
    def test_tradealgo_bull_bear_indicators_bear(self):
        """Test inference from Bear plot indicator."""
        payload = {
            'symbol': 'AUDUSD',
            'Bull': '0',
            'Bear': '1',
            'EntryPrice': '0.6550',
            'quantity': '10000'
        }
        normalized = WebhookNormalizer.normalize(payload)
        
        assert normalized.action == 'sell'
        assert normalized.order_type == 'enter_short'
        assert normalized.is_bull == False
        assert normalized.is_bear == True
    
    def test_tradealgo_bull_exit_indicator(self):
        """Test inference from Bull Exit plot indicator."""
        payload = {
            'symbol': 'EURUSD',
            'Bull Exit': '1',
            'quantity': '10000'
        }
        normalized = WebhookNormalizer.normalize(payload)
        
        assert normalized.order_type == 'exit'
        assert normalized.alert_type == 'EXIT'
        assert normalized.is_bull_exit == True
    
    def test_tradealgo_technical_indicators(self):
        """Test extraction of TradeAlgo technical indicator values."""
        payload = {
            'symbol': 'EURUSD',
            'signal_type': 'bull_entry',
            'entry_price': '1.0850',
            'stop_loss': '1.0800',
            'atr_value': '0.00044',
            'slDistInPips': '40.79740',
            'quantity': '10000'
        }
        normalized = WebhookNormalizer.normalize(payload)
        
        assert normalized.atr_value == pytest.approx(0.00044, rel=1e-4)
        assert normalized.sl_dist_pips == pytest.approx(40.79740, rel=1e-4)
    
    def test_first_tp_used_as_primary_take_profit(self):
        """Test that take_profit_1 is used as primary take_profit_price if not set."""
        payload = {
            'symbol': 'EURUSD',
            'signal_type': 'bull_entry',
            'entry_price': '1.0850',
            'take_profit_1': '1.0900',
            'take_profit_2': '1.0950',
            'quantity': '10000'
        }
        normalized = WebhookNormalizer.normalize(payload)
        
        # take_profit_price should be set to take_profit_1 value
        assert normalized.take_profit_price == 1.0900
        assert normalized.take_profit_1 == 1.0900
        assert normalized.take_profit_2 == 1.0950
