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
 * Supports multiple TP levels (TP1, TP2, TP3).
 * 
 * **Validates: Requirements 1.3, 1.4, 5.3, 5.4**
 * 
 * @param {Object} props
 * @param {number} [props.currentSL] - Current stop loss value
 * @param {number} [props.previousSL] - Previous stop loss value (for change detection)
 * @param {number} [props.currentTP] - Current take profit value (legacy single TP)
 * @param {number} [props.previousTP] - Previous take profit value (for change detection)
 * @param {number} [props.tp1] - Take profit level 1
 * @param {number} [props.tp2] - Take profit level 2
 * @param {number} [props.tp3] - Take profit level 3
 * @param {number} [props.tpCount] - Number of TP levels configured
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
  tp1,
  tp2,
  tp3,
  tpCount = 1,
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

  // Format price for display (5 decimals for forex pipettes)
  const formatPrice = (price) => {
    if (price === null || price === undefined) return 'N/A'
    return parseFloat(price).toFixed(5)
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
    if (!slChanged) return `Stop Loss Set @ ${formatPrice(currentSL)}`
    return `Stop Loss changed\nPrevious: ${formatPrice(previousSL)}\nCurrent: ${formatPrice(currentSL)}`
  }

  // Build tooltip content for TP
  const getTPTooltip = (level, value) => {
    const label = level ? `TP${level}` : 'Take Profit'
    return `${label} Set @ ${formatPrice(value)}`
  }
  
  // Determine which TP values to display
  const tpValues = []
  if (tp1 !== null && tp1 !== undefined) {
    tpValues.push({ level: 1, value: tp1 })
  }
  if (tp2 !== null && tp2 !== undefined) {
    tpValues.push({ level: 2, value: tp2 })
  }
  if (tp3 !== null && tp3 !== undefined) {
    tpValues.push({ level: 3, value: tp3 })
  }
  // Fallback to currentTP if no individual TPs
  if (tpValues.length === 0 && currentTP !== null && currentTP !== undefined) {
    tpValues.push({ level: tpCount > 1 ? 1 : null, value: currentTP })
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
                <Typography 
                  component="span" 
                  sx={{ 
                    fontSize: compact ? '0.6rem' : '0.7rem',
                    fontWeight: 'bold',
                    mr: 0.25
                  }}
                >
                  SL Set @
                </Typography>
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

      {/* Take Profit Display - supports multiple TPs */}
      {tpValues.map(({ level, value }) => (
        <Tooltip 
          key={level || 'tp'}
          title={<Box sx={{ whiteSpace: 'pre-line' }}>{getTPTooltip(level, value)}</Box>} 
          arrow 
          placement="top"
        >
          <Chip
            icon={<TakeProfitIcon sx={{ fontSize: compact ? '0.8rem' : '0.9rem' }} />}
            label={
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25 }}>
                <Typography 
                  component="span" 
                  sx={{ 
                    fontSize: compact ? '0.6rem' : '0.7rem',
                    fontWeight: 'bold',
                    mr: 0.25
                  }}
                >
                  {level ? `TP${level} Set @` : 'TP Set @'}
                </Typography>
                <Typography 
                  component="span" 
                  sx={{ fontSize: compact ? '0.65rem' : '0.75rem' }}
                >
                  {formatPrice(value)}
                </Typography>
              </Box>
            }
            size="small"
            variant="outlined"
            sx={{
              borderColor: 'success.light',
              color: 'success.light',
              bgcolor: 'transparent',
              height: compact ? 22 : 26,
              '& .MuiChip-icon': {
                color: 'success.light'
              },
              transition: 'all 0.3s ease'
            }}
          />
        </Tooltip>
      ))}

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
