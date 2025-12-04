import React from 'react'
import { Box, Tooltip, Typography, Chip } from '@mui/material'
import {
  ArrowUpward as ArrowUpIcon,
  ArrowDownward as ArrowDownIcon,
  Shield as StopLossIcon,
  EmojiEvents as TakeProfitIcon,
  TrendingFlat as TrailingIcon
} from '@mui/icons-material'

/**
 * SLTPChangeIndicator Component
 * 
 * Displays current SL/TP values with change arrows when values differ from previous.
 * Also shows trailing stop information if available.
 * 
 * **Validates: Requirements 1.3, 1.4, 5.3, 5.4**
 * 
 * @param {Object} props
 * @param {number} [props.currentSL] - Current stop loss value
 * @param {number} [props.previousSL] - Previous stop loss value (for change detection)
 * @param {number} [props.currentTP] - Current take profit value
 * @param {number} [props.previousTP] - Previous take profit value (for change detection)
 * @param {number} [props.trailPrice] - Trailing stop price
 * @param {number} [props.trailOffset] - Trailing stop offset
 * @param {boolean} [props.compact=false] - Whether to use compact display mode
 * @param {boolean} [props.showLabels=true] - Whether to show SL/TP labels
 */
const SLTPChangeIndicator = ({
  currentSL,
  previousSL,
  currentTP,
  previousTP,
  trailPrice,
  trailOffset,
  compact = false,
  showLabels = true
}) => {
  // Determine if SL changed and direction
  const slChanged = previousSL !== undefined && previousSL !== null && 
                    currentSL !== undefined && currentSL !== null && 
                    previousSL !== currentSL
  const slIncreased = slChanged && currentSL > previousSL
  const slDecreased = slChanged && currentSL < previousSL

  // Determine if TP changed and direction
  const tpChanged = previousTP !== undefined && previousTP !== null && 
                    currentTP !== undefined && currentTP !== null && 
                    previousTP !== currentTP
  const tpIncreased = tpChanged && currentTP > previousTP
  const tpDecreased = tpChanged && currentTP < previousTP

  // Format price for display
  const formatPrice = (price) => {
    if (price === null || price === undefined) return 'N/A'
    return parseFloat(price).toFixed(4)
  }

  // Render change arrow
  const renderChangeArrow = (increased, decreased) => {
    if (increased) {
      return (
        <ArrowUpIcon 
          sx={{ 
            fontSize: compact ? '0.8rem' : '1rem', 
            color: 'success.light',
            animation: 'pulse 1s ease-in-out'
          }} 
        />
      )
    }
    if (decreased) {
      return (
        <ArrowDownIcon 
          sx={{ 
            fontSize: compact ? '0.8rem' : '1rem', 
            color: 'error.light',
            animation: 'pulse 1s ease-in-out'
          }} 
        />
      )
    }
    return null
  }

  // Build tooltip content for SL
  const getSLTooltip = () => {
    if (!slChanged) return `Stop Loss: ${formatPrice(currentSL)}`
    return `Stop Loss changed\nPrevious: ${formatPrice(previousSL)}\nCurrent: ${formatPrice(currentSL)}`
  }

  // Build tooltip content for TP
  const getTPTooltip = () => {
    if (!tpChanged) return `Take Profit: ${formatPrice(currentTP)}`
    return `Take Profit changed\nPrevious: ${formatPrice(previousTP)}\nCurrent: ${formatPrice(currentTP)}`
  }

  // Build tooltip content for trailing stop
  const getTrailingTooltip = () => {
    const parts = []
    if (trailPrice !== null && trailPrice !== undefined) {
      parts.push(`Trail Price: ${formatPrice(trailPrice)}`)
    }
    if (trailOffset !== null && trailOffset !== undefined) {
      parts.push(`Trail Offset: ${trailOffset}`)
    }
    return parts.join('\n') || 'Trailing Stop'
  }

  const hasTrailingStop = (trailPrice !== null && trailPrice !== undefined) || 
                          (trailOffset !== null && trailOffset !== undefined)

  // If no data to display, return null
  if (currentSL === null && currentSL === undefined && 
      currentTP === null && currentTP === undefined && 
      !hasTrailingStop) {
    return null
  }

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: compact ? 0.5 : 1, flexWrap: 'wrap' }}>
      {/* Stop Loss Display */}
      {(currentSL !== null && currentSL !== undefined) && (
        <Tooltip 
          title={<Box sx={{ whiteSpace: 'pre-line' }}>{getSLTooltip()}</Box>} 
          arrow 
          placement="top"
        >
          <Chip
            icon={<StopLossIcon sx={{ fontSize: compact ? '0.8rem' : '0.9rem' }} />}
            label={
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25 }}>
                {showLabels && (
                  <Typography 
                    component="span" 
                    sx={{ 
                      fontSize: compact ? '0.6rem' : '0.7rem',
                      fontWeight: 'bold',
                      mr: 0.25
                    }}
                  >
                    SL:
                  </Typography>
                )}
                <Typography 
                  component="span" 
                  sx={{ fontSize: compact ? '0.65rem' : '0.75rem' }}
                >
                  {formatPrice(currentSL)}
                </Typography>
                {renderChangeArrow(slIncreased, slDecreased)}
              </Box>
            }
            size="small"
            variant="outlined"
            sx={{
              borderColor: slChanged ? (slIncreased ? 'success.main' : 'error.main') : 'error.light',
              color: slChanged ? (slIncreased ? 'success.light' : 'error.light') : 'error.light',
              bgcolor: slChanged ? 'rgba(244, 67, 54, 0.1)' : 'transparent',
              height: compact ? 22 : 26,
              '& .MuiChip-icon': {
                color: 'error.light'
              },
              transition: 'all 0.3s ease',
              ...(slChanged && {
                boxShadow: slIncreased 
                  ? '0 0 8px rgba(76, 175, 80, 0.4)' 
                  : '0 0 8px rgba(244, 67, 54, 0.4)'
              })
            }}
          />
        </Tooltip>
      )}

      {/* Take Profit Display */}
      {(currentTP !== null && currentTP !== undefined) && (
        <Tooltip 
          title={<Box sx={{ whiteSpace: 'pre-line' }}>{getTPTooltip()}</Box>} 
          arrow 
          placement="top"
        >
          <Chip
            icon={<TakeProfitIcon sx={{ fontSize: compact ? '0.8rem' : '0.9rem' }} />}
            label={
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25 }}>
                {showLabels && (
                  <Typography 
                    component="span" 
                    sx={{ 
                      fontSize: compact ? '0.6rem' : '0.7rem',
                      fontWeight: 'bold',
                      mr: 0.25
                    }}
                  >
                    TP:
                  </Typography>
                )}
                <Typography 
                  component="span" 
                  sx={{ fontSize: compact ? '0.65rem' : '0.75rem' }}
                >
                  {formatPrice(currentTP)}
                </Typography>
                {renderChangeArrow(tpIncreased, tpDecreased)}
              </Box>
            }
            size="small"
            variant="outlined"
            sx={{
              borderColor: tpChanged ? (tpIncreased ? 'success.main' : 'warning.main') : 'success.light',
              color: tpChanged ? (tpIncreased ? 'success.light' : 'warning.light') : 'success.light',
              bgcolor: tpChanged ? 'rgba(76, 175, 80, 0.1)' : 'transparent',
              height: compact ? 22 : 26,
              '& .MuiChip-icon': {
                color: 'success.light'
              },
              transition: 'all 0.3s ease',
              ...(tpChanged && {
                boxShadow: tpIncreased 
                  ? '0 0 8px rgba(76, 175, 80, 0.4)' 
                  : '0 0 8px rgba(255, 152, 0, 0.4)'
              })
            }}
          />
        </Tooltip>
      )}

      {/* Trailing Stop Display */}
      {hasTrailingStop && (
        <Tooltip 
          title={<Box sx={{ whiteSpace: 'pre-line' }}>{getTrailingTooltip()}</Box>} 
          arrow 
          placement="top"
        >
          <Chip
            icon={<TrailingIcon sx={{ fontSize: compact ? '0.8rem' : '0.9rem' }} />}
            label={
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25 }}>
                {showLabels && (
                  <Typography 
                    component="span" 
                    sx={{ 
                      fontSize: compact ? '0.6rem' : '0.7rem',
                      fontWeight: 'bold',
                      mr: 0.25
                    }}
                  >
                    Trail:
                  </Typography>
                )}
                <Typography 
                  component="span" 
                  sx={{ fontSize: compact ? '0.65rem' : '0.75rem' }}
                >
                  {trailPrice !== null && trailPrice !== undefined 
                    ? formatPrice(trailPrice) 
                    : `±${trailOffset}`}
                </Typography>
              </Box>
            }
            size="small"
            variant="outlined"
            sx={{
              borderColor: 'warning.main',
              color: 'warning.light',
              height: compact ? 22 : 26,
              '& .MuiChip-icon': {
                color: 'warning.light'
              }
            }}
          />
        </Tooltip>
      )}
    </Box>
  )
}

export default SLTPChangeIndicator
