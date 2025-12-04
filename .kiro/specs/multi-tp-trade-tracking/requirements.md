# Requirements Document

## Introduction

This feature improves the webhook trading system's ability to track and display multi-take-profit (TP) strategy trades from TradingView. The system receives webhook alerts for trade entries, multiple TP exits (TP1, TP2, TP3), stop-loss exits, and position closures. The goal is to accurately group these alerts into coherent trade lifecycles, track position size changes through each TP hit, calculate P&L at each stage, and present this information clearly in the UI timeline.

## Glossary

- **Trade Group**: A collection of related webhook alerts that form a complete trade lifecycle from entry to full exit
- **Take Profit (TP)**: A partial or full position exit at a predetermined profit target (TP1, TP2, TP3)
- **Position Size**: The remaining quantity of contracts/units still open after each trade action
- **Entry Alert**: A webhook with `order_type` containing `enter_long` or `enter_short`
- **Reduce Alert**: A webhook with `order_type` containing `reduce_long` or `reduce_short`, typically a TP hit
- **Flat Position**: When `market_position` is "flat" and `position_size` is "0", indicating the trade is fully closed
- **Trade Lifecycle**: The complete sequence from entry through all TPs/exits to flat position
- **Realized P&L**: Profit/loss calculated from executed exit prices vs entry price

## Requirements

### Requirement 1

**User Story:** As a trader, I want the system to accurately track position size changes through each TP hit, so that I can see how much of my position remains open at any point.

#### Acceptance Criteria

1. WHEN a reduce alert is received THEN the System SHALL extract and store the `position_size` value from the webhook metadata
2. WHEN displaying a trade group THEN the System SHALL show the remaining position size after each TP hit
3. WHEN `position_size` is "0" and `market_position` is "flat" THEN the System SHALL mark the trade group as fully closed
4. WHEN a new entry alert is received after a flat position THEN the System SHALL create a new trade group

### Requirement 2

**User Story:** As a trader, I want to see the P&L calculated for each individual TP level, so that I can understand the profitability of each exit point.

#### Acceptance Criteria

1. WHEN a TP exit is recorded THEN the System SHALL calculate the P&L percentage using the formula: ((exit_price - entry_price) / entry_price) * 100 for longs
2. WHEN a TP exit is recorded for a short position THEN the System SHALL calculate P&L using: ((entry_price - exit_price) / entry_price) * 100
3. WHEN displaying a trade group THEN the System SHALL show individual P&L for each TP level (TP1, TP2, TP3)
4. WHEN displaying a closed trade group THEN the System SHALL show the weighted average P&L based on quantities at each exit

### Requirement 3

**User Story:** As a trader, I want the UI timeline to clearly show the progression of my trade from entry through each TP hit to closure, so that I can visualize the complete trade lifecycle.

#### Acceptance Criteria

1. WHEN displaying a trade timeline THEN the System SHALL show entries in chronological order with visual connectors
2. WHEN displaying a TP hit THEN the System SHALL show the TP level (TP1/TP2/TP3), exit price, quantity sold, and remaining position size
3. WHEN displaying the entry THEN the System SHALL show the entry price, total quantity, leverage, and stop-loss price if available
4. WHEN a trade group is fully closed THEN the System SHALL display a summary showing total P&L, duration, and all TP levels hit

### Requirement 4

**User Story:** As a trader, I want the system to correctly identify TP levels from webhook data, so that alerts are properly categorized in the timeline.

#### Acceptance Criteria

1. WHEN a webhook contains `order_comment` with "TP1", "TP2", or "TP3" THEN the System SHALL categorize the alert as that specific TP level
2. WHEN a webhook contains `order_id` with "1st Target", "2nd Target", or "3rd Target" THEN the System SHALL map these to TP1, TP2, TP3 respectively
3. WHEN a webhook has `order_type` of `reduce_long` or `reduce_short` without TP identifiers THEN the System SHALL categorize it as a generic "Partial Close"
4. WHEN categorizing alerts THEN the System SHALL prioritize `order_comment` over `order_id` for TP level detection

### Requirement 5

**User Story:** As a trader, I want to see key trade metadata (leverage, stop-loss) displayed prominently, so that I can quickly understand the trade parameters.

#### Acceptance Criteria

1. WHEN displaying a trade group header THEN the System SHALL show the leverage value from the entry alert
2. WHEN an entry alert contains `stop_loss_price` THEN the System SHALL display the stop-loss level in the trade group header
3. WHEN displaying individual timeline entries THEN the System SHALL show the leverage if it differs from the group's entry leverage
4. WHEN a stop-loss exit occurs THEN the System SHALL highlight it distinctly from TP exits in the timeline

### Requirement 6

**User Story:** As a trader, I want the system to handle multiple concurrent trades on the same symbol, so that overlapping strategies are tracked separately.

#### Acceptance Criteria

1. WHEN a new entry alert arrives while an existing trade group for the same symbol is still open THEN the System SHALL create a new separate trade group
2. WHEN matching reduce alerts to trade groups THEN the System SHALL use timestamp proximity and position size continuity to determine the correct group
3. WHEN displaying multiple active trade groups for the same symbol THEN the System SHALL visually distinguish them with unique identifiers
