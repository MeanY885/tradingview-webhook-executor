import React, { useMemo } from 'react'
import { Box, Tooltip, Typography, Chip } from '@mui/material'
import {
  CheckBox as CheckedIcon,
  CheckBoxOutlineBlank as UncheckedIcon,
  EmojiEvents as TrophyIcon
} from '@mui/icons-material'
import { getTPHitStatus, getTPTooltipMessage } from '../../utils/tpHitDetection'

/**
 * TPCheckboxes Component
 * 
 * Displays checkbox indicators for TP1, TP2, TP3 showing which take profit
 * levels have been hit for a trade group.
 * 
 * **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**
 * 
 * @param {Object} props
 * @param {Object[]} props.trades - Array of webhook/trade objects in the trade group
 * @param {boolean} [props.compact=false] - Whether to use compact display mode
 * @param {boolean} [props.showCompleteIndicator=true] - Whether to show "complete" indicator
 */
const TPCheckboxes = ({ trades, compact = false, showCompleteIndicator = true }) => {
  const tpStatus = useMemo(() => getTPHitStatus(trades), [trades])

  // Get TP info by level
  const getTPInfo = (level) => {
    return tpStatus.tpDetails.find(tp => tp.level === level) || {
      level,
      isHit: false,
      timestamp: null,
      exitPrice: null,
      pnlPercent: null
    }
  }

  const tp1Info = getTPInfo('TP1')
  const tp2Info = getTPInfo('TP2')
  const tp3Info = getTPInfo('TP3')

  const renderTPCheckbox = (tpInfo) => {
    const isHit = tpInfo.isHit
    const tooltipContent = getTPTooltipMessage(tpInfo)

    return (
      <Tooltip
        key={tpInfo.level}
        title={
          <Box sx={{ whiteSpace: 'pre-line' }}>
            {tooltipContent}
          </Box>
        }
        arrow
        placement="top"
      >
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 0.25,
            cursor: 'default',
            px: compact ? 0.5 : 0.75,
            py: compact ? 0.25 : 0.5,
            borderRadius: 1,
            bgcolor: isHit ? 'success.dark' : 'action.hover',
            transition: 'all 0.2s ease',
            '&:hover': {
              bgcolor: isHit ? 'success.main' : 'action.selected'
            }
          }}
        >
          {isHit ? (
            <CheckedIcon
              sx={{
                fontSize: compact ? '0.9rem' : '1.1rem',
                color: 'success.light'
              }}
            />
          ) : (
            <UncheckedIcon
              sx={{
                fontSize: compact ? '0.9rem' : '1.1rem',
                color: 'text.disabled'
              }}
            />
          )}
          <Typography
            variant="caption"
            sx={{
              fontWeight: isHit ? 'bold' : 'normal',
              color: isHit ? 'success.light' : 'text.secondary',
              fontSize: compact ? '0.65rem' : '0.7rem'
            }}
          >
            {tpInfo.level}
          </Typography>
        </Box>
      </Tooltip>
    )
  }

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
      {renderTPCheckbox(tp1Info)}
      {renderTPCheckbox(tp2Info)}
      {renderTPCheckbox(tp3Info)}
      
      {/* Complete indicator when all TPs hit */}
      {showCompleteIndicator && tpStatus.allTpsComplete && (
        <Tooltip title="All take profit levels hit!" arrow placement="top">
          <Chip
            icon={<TrophyIcon sx={{ fontSize: '0.9rem' }} />}
            label="Complete"
            size="small"
            sx={{
              ml: 0.5,
              bgcolor: 'warning.dark',
              color: 'warning.contrastText',
              fontWeight: 'bold',
              fontSize: '0.65rem',
              height: compact ? 20 : 24,
              '& .MuiChip-icon': {
                color: 'warning.contrastText'
              }
            }}
          />
        </Tooltip>
      )}
    </Box>
  )
}

export default TPCheckboxes
