# Requirements Document

## Introduction

This feature enhances the TradingView webhook trading system with four key improvements: (1) tracking and displaying stop loss and take profit value changes from webhook updates, (2) supporting flexible JSON webhook formats from different trading strategies and exchanges, (3) providing a visual checkbox system to show which take profit levels have been hit for each trade, and (4) adding password management capabilities for users in system settings.

## Glossary

- **Stop Loss (SL)**: A price level at which a position is automatically closed to limit losses
- **Take Profit (TP)**: A price level at which a position is automatically closed to secure profits (TP1, TP2, TP3)
- **Webhook**: An HTTP callback containing trade alert data from TradingView
- **Trade Group**: A collection of related webhook alerts forming a complete trade lifecycle
- **Exit Strategy Fields**: TradingView fields like `exit_stop`, `exit_limit`, `exit_loss_ticks`, `exit_profit_ticks` that define exit parameters
- **TP Hit Indicator**: A visual checkbox showing whether a specific take profit level has been reached
- **Password Hash**: A cryptographically secure representation of a user password

## Requirements

### Requirement 1

**User Story:** As a trader, I want to see when my stop loss or take profit values change during a trade, so that I can track strategy adjustments in real-time.

#### Acceptance Criteria

1. WHEN a webhook contains `exit_stop`, `exit_limit`, or `stop_loss_price` fields THEN the System SHALL extract and store these values
2. WHEN a webhook contains `exit_loss_ticks` or `exit_profit_ticks` fields THEN the System SHALL extract and store these values
3. WHEN displaying a trade timeline entry THEN the System SHALL show the current SL/TP values if they differ from the previous entry
4. WHEN SL or TP values change between consecutive webhooks in a trade group THEN the System SHALL highlight the change visually
5. WHEN a trade group header is displayed THEN the System SHALL show the most recent SL and TP values

### Requirement 2

**User Story:** As a trader using different TradingView strategies, I want the system to correctly parse webhooks regardless of JSON format variations, so that all my strategies work correctly.

#### Acceptance Criteria

1. WHEN a webhook contains `exit_stop` or `exit_limit` fields (TradingView strategy format) THEN the System SHALL map these to stop_loss_price and take_profit_price respectively
2. WHEN a webhook contains `exit_trail_price` and `exit_trail_offset` fields THEN the System SHALL extract and store trailing stop parameters
3. WHEN a webhook uses `ticker` instead of `symbol` for the instrument name THEN the System SHALL correctly identify the trading symbol
4. WHEN a webhook contains `position_avg_price` THEN the System SHALL use this as the entry price for P&L calculations
5. WHEN a webhook contains plot fields (`plot_0`, `plot_1`, etc.) THEN the System SHALL store these as custom indicator values in metadata
6. WHEN parsing webhook JSON THEN the System SHALL handle both string and numeric values for price and quantity fields

### Requirement 3

**User Story:** As a trader, I want to see checkboxes indicating which take profit levels have been hit for each trade, so that I can quickly assess trade progress.

#### Acceptance Criteria

1. WHEN displaying a trade group THEN the System SHALL show checkbox indicators for TP1, TP2, and TP3
2. WHEN a TP level has been hit (webhook received with that TP level) THEN the System SHALL display the corresponding checkbox as checked/filled
3. WHEN a TP level has not been hit THEN the System SHALL display the corresponding checkbox as unchecked/empty
4. WHEN hovering over a TP checkbox THEN the System SHALL show a tooltip with the hit timestamp and exit price if available
5. WHEN all configured TP levels have been hit THEN the System SHALL display a visual indicator of complete TP execution

### Requirement 4

**User Story:** As a system administrator, I want to change user passwords from the settings page, so that I can help users who have forgotten their credentials.

#### Acceptance Criteria

1. WHEN an administrator accesses the settings page THEN the System SHALL display a password change section
2. WHEN changing a password THEN the System SHALL require the current password for verification (for self-change) OR admin privileges (for other users)
3. WHEN a new password is submitted THEN the System SHALL validate minimum length of 8 characters
4. WHEN a valid new password is submitted THEN the System SHALL hash the password using bcrypt before storage
5. WHEN password change succeeds THEN the System SHALL display a success confirmation message
6. WHEN password change fails THEN the System SHALL display an appropriate error message without revealing sensitive details

### Requirement 5

**User Story:** As a trader, I want the system to track trailing stop information, so that I can see how my trailing stops are being managed.

#### Acceptance Criteria

1. WHEN a webhook contains `exit_trail_price` THEN the System SHALL store the current trailing stop price
2. WHEN a webhook contains `exit_trail_offset` THEN the System SHALL store the trailing stop offset value
3. WHEN displaying trade details THEN the System SHALL show trailing stop information if available
4. WHEN trailing stop values change between webhooks THEN the System SHALL highlight the change in the timeline

