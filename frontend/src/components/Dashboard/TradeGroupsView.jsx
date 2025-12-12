import React, { useState, useMemo } from 'react'
import {
  Box, Card, CardContent, Collapse, Typography, IconButton,
  Chip, Divider, List, ListItem, Avatar, Tooltip, Stack,
  LinearProgress, Paper, Button, CircularProgress
} from '@mui/material'
import {
  ExpandMore as ExpandMoreIcon,
  TrendingUp as EntryIcon,
  TrendingDown as ExitIcon,
  TrendingUp,
  TrendingDown,
  CrisisAlert as StopLossIcon,
  EmojiEvents as TakeProfitIcon,
  CheckCircle as SuccessIcon,
  Delete as DeleteIcon,
  Speed as LeverageIcon,
  Shield as StopLossShieldIcon,
  Timer as DurationIcon,
  Refresh as RefreshIcon
} from '@mui/icons-material'
import { format, formatDistanceStrict } from 'date-fns'
import api from '../../services/api'
import TPCheckboxes from './TPCheckboxes'
import SLTPChangeIndicator from './SLTPChangeIndicator'
import WebhookDetailModal from './WebhookDetailModal'

const TradeGroupsView = ({ webhooks, onWebhookDeleted, onRefresh }) => {
  const [expandedGroups, setExpandedGroups] = useState({})
  const [reprocessing, setReprocessing] = useState(false)
  const [selectedWebhook, setSelectedWebhook] = useState(null)
  const [modalOpen, setModalOpen] = useState(false)

  // Group webhooks by trade_group_id
  const groupedTrades = useMemo(() => {
    return webhooks.reduce((groups, webhook) => {
      const groupId = webhook.trade_group_id || `ungrouped-${webhook.id}`
      if (!groups[groupId]) {
        groups[groupId] = []
      }
      groups[groupId].push(webhook)
      return groups
    }, {})
  }, [webhooks])

  // Sort groups by most recent first
  const sortedGroups = useMemo(() => {
    return Object.entries(groupedTrades).sort((a, b) => {
      const aTime = new Date(a[1][0].timestamp).getTime()
      const bTime = new Date(b[1][0].timestamp).getTime()
      return bTime - aTime
    })
  }, [groupedTrades])

  const toggleGroup = (groupId) => {
    setExpandedGroups(prev => ({
      ...prev,
      [groupId]: !prev[groupId]
    }))
  }

  const handleTradeClick = (e, trade) => {
    e.stopPropagation()
    setSelectedWebhook(trade)
    setModalOpen(true)
  }

  const handleCloseModal = () => {
    setModalOpen(false)
    setSelectedWebhook(null)
  }

  const handleWebhookUpdated = (updatedWebhook) => {
    setSelectedWebhook(updatedWebhook)
    if (onRefresh) {
      onRefresh()
    }
  }

  const determineActionType = (webhook) => {
    // Use tp_level from backend if available
    if (webhook.tp_level) {
      if (webhook.tp_level === 'ENTRY') return 'Entry'
      if (webhook.tp_level === 'TP1') return 'TP1'
      if (webhook.tp_level === 'TP2') return 'TP2'
      if (webhook.tp_level === 'TP3') return 'TP3'
      if (webhook.tp_level === 'SL') return 'SL Close'
      if (webhook.tp_level === 'PARTIAL') return 'Partial'
    }

    // Fallback to manual detection
    const comment = webhook.metadata?.order_comment?.toLowerCase() || ''
    const orderId = webhook.metadata?.order_id?.toLowerCase() || ''
    const alertMessage = webhook.metadata?.alert_message_params?.order_type?.toLowerCase() || ''

    if (alertMessage.includes('enter_long') || alertMessage.includes('enter_short')) {
      return 'Entry'
    }
    if (comment.includes('tp1') || orderId.includes('1st target')) return 'TP1'
    if (comment.includes('tp2') || orderId.includes('2nd target')) return 'TP2'
    if (comment.includes('tp3') || orderId.includes('3rd target')) return 'TP3'
    if (comment.includes('sl') || comment.includes('stop loss')) return 'SL Close'
    if (alertMessage.includes('reduce')) return 'Partial'
    if (webhook.action === 'buy' && !comment) return 'Entry'
    return 'Close'
  }

  const getActionIcon = (actionType, direction) => {
    const isLong = direction === 'long'
    switch (actionType) {
      case 'Entry':
        return <EntryIcon sx={{ color: isLong ? 'success.main' : 'error.main' }} />
      case 'TP1':
      case 'TP2':
      case 'TP3':
        return <TakeProfitIcon sx={{ color: 'success.light' }} />
      case 'SL Close':
        return <StopLossIcon sx={{ color: 'error.light' }} />
      default:
        return <ExitIcon sx={{ color: 'text.secondary' }} />
    }
  }

  // Get entry trade metadata (leverage, stop_loss)
  const getEntryMetadata = (trades) => {
    const sortedTrades = [...trades].sort((a, b) =>
      new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    )
    const entry = sortedTrades.find(t => {
      const actionType = determineActionType(t)
      return actionType === 'Entry'
    }) || sortedTrades[0]

    return {
      leverage: entry?.leverage || entry?.metadata?.alert_message_params?.leverage || null,
      stopLoss: entry?.stop_loss || entry?.metadata?.alert_message_params?.stop_loss_price || null,
      entryPrice: entry?.entry_price || entry?.price || entry?.metadata?.order_price || null,
      entryQuantity: entry?.quantity || entry?.metadata?.order_contracts || null
    }
  }

  // Calculate total P&L from individual exit P&Ls or compute manually
  const calculateGroupPnL = (trades, direction) => {
    const sortedTrades = [...trades].sort((a, b) =>
      new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    )

    // Try to use pre-calculated P&L values from backend
    const exitsWithPnL = sortedTrades.filter(t => 
      t.realized_pnl_percent !== null && t.realized_pnl_percent !== undefined
    )

    if (exitsWithPnL.length > 0) {
      let totalWeightedPnL = 0
      let totalQuantity = 0

      exitsWithPnL.forEach(exit => {
        const qty = exit.quantity || 1
        totalWeightedPnL += exit.realized_pnl_percent * qty
        totalQuantity += qty
      })

      return totalQuantity > 0 ? totalWeightedPnL / totalQuantity : 0
    }

    // Fallback to manual calculation
    const entry = sortedTrades.find(t => determineActionType(t) === 'Entry')
    const exits = sortedTrades.filter(t => {
      const actionType = determineActionType(t)
      return actionType !== 'Entry'
    })

    if (!entry || exits.length === 0) return null

    const entryPrice = entry.entry_price || entry.price || entry.metadata?.order_price
    let totalPnL = 0
    let totalQuantity = 0

    exits.forEach(exit => {
      const exitPrice = exit.price || exit.metadata?.order_price
      const quantity = exit.quantity || 1
      if (entryPrice && exitPrice) {
        let pnl
        if (direction === 'short') {
          pnl = ((entryPrice - exitPrice) / entryPrice) * 100
        } else {
          pnl = ((exitPrice - entryPrice) / entryPrice) * 100
        }
        totalPnL += pnl * quantity
        totalQuantity += quantity
      }
    })

    return totalQuantity > 0 ? totalPnL / totalQuantity : null
  }

  const getTradeStatus = (trades) => {
    const hasFlat = trades.some(t => t.metadata?.market_position === 'flat')
    const hasZeroPosition = trades.some(t => 
      t.position_size_after === 0 || t.metadata?.position_size === '0'
    )

    if (hasFlat || hasZeroPosition) return 'CLOSED'
    return 'ACTIVE'
  }

  // Determine exit type for closed trades
  const getExitType = (trades) => {
    const sortedTrades = [...trades].sort((a, b) =>
      new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    )
    
    for (const trade of sortedTrades) {
      const actionType = determineActionType(trade)
      if (actionType === 'SL Close') return 'SL'
      if (['TP1', 'TP2', 'TP3'].includes(actionType)) return 'TP'
    }
    return 'MANUAL'
  }

  // Calculate trade duration
  const getTradeDuration = (trades) => {
    const sortedTrades = [...trades].sort((a, b) =>
      new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    )
    
    if (sortedTrades.length < 2) return null
    
    const firstTrade = sortedTrades[0]
    const lastTrade = sortedTrades[sortedTrades.length - 1]
    
    return formatDistanceStrict(
      new Date(firstTrade.timestamp),
      new Date(lastTrade.timestamp)
    )
  }

  // Calculate position reduction percentage for progress bar
  const getPositionProgress = (trade, entryQuantity) => {
    if (!entryQuantity || entryQuantity === 0) return 0
    const remaining = trade.position_size_after ?? entryQuantity
    const reduced = entryQuantity - remaining
    return Math.min(100, Math.max(0, (reduced / entryQuantity) * 100))
  }

  // Get SL/TP values from a trade - Task 10.2
  const getSLTPValues = (trade) => {
    // Extract individual TP levels from metadata
    const tpLevels = trade.metadata?.take_profit_levels || {}
    const tp1 = tpLevels.take_profit_1 ?? null
    const tp2 = tpLevels.take_profit_2 ?? null
    const tp3 = tpLevels.take_profit_3 ?? null
    
    return {
      currentSL: trade.current_stop_loss ?? trade.stop_loss ?? 
                 trade.metadata?.alert_message_params?.stop_loss_price ?? null,
      currentTP: trade.current_take_profit ?? trade.take_profit ?? 
                 trade.metadata?.alert_message_params?.take_profit_price ?? null,
      tp1,
      tp2,
      tp3,
      tpCount: trade.metadata?.tp_count ?? (tp3 ? 3 : tp2 ? 2 : tp1 ? 1 : 0),
      trailPrice: trade.exit_trail_price ?? null,
      trailOffset: trade.exit_trail_offset ?? null,
      slChanged: trade.sl_changed ?? false,
      tpChanged: trade.tp_changed ?? false
    }
  }

  // Get previous trade's SL/TP values for change comparison - Task 10.2
  const getPreviousSLTP = (sortedTrades, currentIndex) => {
    if (currentIndex <= 0) return { previousSL: null, previousTP: null }
    const prevTrade = sortedTrades[currentIndex - 1]
    const prevValues = getSLTPValues(prevTrade)
    return {
      previousSL: prevValues.currentSL,
      previousTP: prevValues.currentTP
    }
  }

  const handleDeleteGroup = async (e, groupId, trades) => {
    e.stopPropagation()

    if (!window.confirm(`Delete entire trade group with ${trades.length} entries?`)) {
      return
    }

    try {
      await Promise.all(trades.map(trade =>
        api.delete(`/api/webhook-logs/${trade.id}`)
      ))

      trades.forEach(trade => {
        if (onWebhookDeleted) {
          onWebhookDeleted(trade.id)
        }
      })
    } catch (error) {
      console.error('Error deleting trade group:', error)
      alert('Failed to delete trade group')
    }
  }

  const handleReprocessSingle = async (e, trade) => {
    e.stopPropagation()
    setReprocessing(true)
    try {
      await api.post(`/api/webhook-logs/${trade.id}/reprocess`)
      if (onRefresh) {
        onRefresh()
      }
    } catch (error) {
      console.error('Error reprocessing webhook:', error)
      alert(error.response?.data?.error || 'Failed to reprocess webhook')
    } finally {
      setReprocessing(false)
    }
  }

  const handleReprocessAllErrors = async () => {
    setReprocessing(true)
    try {
      const response = await api.post('/api/webhook-logs/reprocess-all-errors')
      alert(`Reprocessed ${response.data.succeeded} of ${response.data.total} webhooks`)
      if (onRefresh) {
        onRefresh()
      }
    } catch (error) {
      console.error('Error reprocessing all errors:', error)
      alert(error.response?.data?.error || 'Failed to reprocess webhooks')
    } finally {
      setReprocessing(false)
    }
  }

  // Check if there are any parse errors
  const hasParseErrors = webhooks.some(w => w.status === 'parse_error' || w.status === 'invalid')

  // Format P&L display
  const formatPnL = (pnl, showSign = true) => {
    if (pnl === null || pnl === undefined) return 'N/A'
    const sign = showSign && pnl >= 0 ? '+' : ''
    return `${sign}${pnl.toFixed(2)}%`
  }

  if (sortedGroups.length === 0) {
    return (
      <Typography color="text.secondary" align="center" sx={{ py: 4 }}>
        No trades yet. Waiting for TradingView alerts...
      </Typography>
    )
  }

  return (
    <Stack spacing={2}>
      {/* Reprocess All Errors Button */}
      {hasParseErrors && (
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 1 }}>
          <Button
            variant="outlined"
            color="warning"
            size="small"
            startIcon={reprocessing ? <CircularProgress size={16} /> : <RefreshIcon />}
            onClick={handleReprocessAllErrors}
            disabled={reprocessing}
          >
            {reprocessing ? 'Reprocessing...' : 'Reprocess All Errors'}
          </Button>
        </Box>
      )}
      {sortedGroups.map(([groupId, trades]) => {
        const isExpanded = expandedGroups[groupId]
        const direction = trades[0]?.trade_direction
        const symbol = trades[0]?.symbol
        const status = getTradeStatus(trades)
        const pnl = calculateGroupPnL(trades, direction)
        const entryMeta = getEntryMetadata(trades)
        const exitType = getExitType(trades)
        const duration = getTradeDuration(trades)

        // Sort trades chronologically for display
        const sortedTrades = [...trades].sort((a, b) =>
          new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
        )
        const latestTrade = sortedTrades[sortedTrades.length - 1]

        return (
          <Card
            key={groupId}
            elevation={isExpanded ? 8 : 2}
            sx={{
              transition: 'all 0.3s ease',
              borderLeft: 4,
              borderColor: direction === 'long' ? 'success.main' : 'error.main',
              '&:hover': {
                elevation: 6,
                transform: 'translateY(-2px)'
              }
            }}
          >
            <CardContent
              onClick={() => toggleGroup(groupId)}
              sx={{
                cursor: 'pointer',
                '&:hover': { bgcolor: 'action.hover' }
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flex: 1, flexWrap: 'wrap' }}>
                  <IconButton
                    sx={{
                      transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                      transition: 'transform 0.3s'
                    }}
                  >
                    <ExpandMoreIcon />
                  </IconButton>

                  {/* Direction Badge */}
                  <Chip
                    label={direction?.toUpperCase() || 'N/A'}
                    size="small"
                    sx={{
                      bgcolor: direction === 'long' ? 'success.main' : 'error.main',
                      color: 'white',
                      fontWeight: 'bold',
                      fontSize: '0.75rem'
                    }}
                  />

                  {/* Symbol & Trade Count */}
                  <Box>
                    <Typography variant="h6" component="span" sx={{ fontWeight: 'bold' }}>
                      {symbol}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                      {trades.length} {trades.length === 1 ? 'order' : 'orders'}
                    </Typography>
                  </Box>

                  {/* Leverage Badge - Task 7.1 */}
                  {entryMeta.leverage && (
                    <Tooltip title="Leverage">
                      <Chip
                        icon={<LeverageIcon sx={{ fontSize: '0.9rem' }} />}
                        label={`${entryMeta.leverage}x`}
                        size="small"
                        variant="outlined"
                        sx={{ 
                          fontWeight: 'bold',
                          borderColor: 'warning.main',
                          color: 'warning.main'
                        }}
                      />
                    </Tooltip>
                  )}

                  {/* Stop Loss Badge - Task 7.1 */}
                  {entryMeta.stopLoss && (
                    <Tooltip title="Stop Loss Price">
                      <Chip
                        icon={<StopLossShieldIcon sx={{ fontSize: '0.9rem' }} />}
                        label={`SL: ${parseFloat(entryMeta.stopLoss).toFixed(4)}`}
                        size="small"
                        variant="outlined"
                        sx={{ 
                          fontWeight: 'bold',
                          borderColor: 'error.light',
                          color: 'error.light'
                        }}
                      />
                    </Tooltip>
                  )}

                  {/* Entry → Exit (only show Exit for closed trades) */}
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Chip
                      label={`Entry: ${entryMeta.entryPrice ? parseFloat(entryMeta.entryPrice).toFixed(4) : 'N/A'}`}
                      size="small"
                      variant="outlined"
                    />
                    {status === 'CLOSED' && (
                      <>
                        <Typography color="text.disabled">→</Typography>
                        <Chip
                          label={`Exit: ${latestTrade?.price || latestTrade?.metadata?.order_price || 'N/A'}`}
                          size="small"
                          variant="outlined"
                        />
                      </>
                    )}
                  </Box>

                  {/* P&L */}
                  {pnl !== null && (
                    <Chip
                      icon={pnl >= 0 ? <TrendingUp fontSize="small" /> : <TrendingDown fontSize="small" />}
                      label={formatPnL(pnl)}
                      size="small"
                      sx={{
                        bgcolor: pnl >= 0 ? 'success.dark' : 'error.dark',
                        color: 'white',
                        fontWeight: 'bold'
                      }}
                    />
                  )}

                  {/* TP Checkboxes - Task 9.1 */}
                  <TPCheckboxes trades={trades} compact={true} showCompleteIndicator={true} />

                  {/* Status */}
                  <Chip
                    label={status}
                    size="small"
                    icon={status === 'CLOSED' ? <SuccessIcon /> : undefined}
                    color={status === 'CLOSED' ? 'default' : 'primary'}
                    variant="outlined"
                  />
                </Box>

                {/* Actions */}
                <Box sx={{ display: 'flex', gap: 1 }}>
                  <Tooltip title="Delete entire trade group">
                    <IconButton
                      size="small"
                      onClick={(e) => handleDeleteGroup(e, groupId, trades)}
                      sx={{
                        color: 'error.main',
                        '&:hover': { bgcolor: 'error.dark', color: 'white' }
                      }}
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </Box>
              </Box>

              {/* Group ID */}
              <Typography
                variant="caption"
                sx={{
                  fontFamily: 'monospace',
                  color: 'text.disabled',
                  mt: 1,
                  display: 'block',
                  fontSize: '0.7rem'
                }}
              >
                {groupId}
              </Typography>
            </CardContent>

            {/* Expanded Timeline */}
            <Collapse in={isExpanded} timeout="auto" unmountOnExit>
              <Divider />
              <CardContent sx={{ bgcolor: 'background.default' }}>
                {/* Trade Group Summary for Closed Trades - Task 7.4 */}
                {status === 'CLOSED' && (
                  <Paper 
                    elevation={0} 
                    sx={{ 
                      p: 2, 
                      mb: 2, 
                      bgcolor: pnl >= 0 ? 'success.dark' : 'error.dark',
                      borderRadius: 2
                    }}
                  >
                    <Typography variant="subtitle2" sx={{ color: 'white', mb: 1, fontWeight: 'bold' }}>
                      Trade Summary
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap', alignItems: 'center' }}>
                      {/* Total P&L */}
                      <Box>
                        <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)' }}>
                          Total P&L
                        </Typography>
                        <Typography variant="h6" sx={{ color: 'white', fontWeight: 'bold' }}>
                          {formatPnL(pnl)}
                        </Typography>
                      </Box>

                      {/* Duration */}
                      {duration && (
                        <Box>
                          <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)' }}>
                            Duration
                          </Typography>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                            <DurationIcon sx={{ color: 'white', fontSize: '1rem' }} />
                            <Typography variant="body2" sx={{ color: 'white' }}>
                              {duration}
                            </Typography>
                          </Box>
                        </Box>
                      )}

                      {/* TP Levels Hit - Task 9.2: Enhanced with TPCheckboxes */}
                      <Box>
                        <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)' }}>
                          TP Levels
                        </Typography>
                        <TPCheckboxes 
                          trades={trades} 
                          compact={false} 
                          showCompleteIndicator={true} 
                        />
                      </Box>

                      {/* Exit Type */}
                      <Box>
                        <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)' }}>
                          Exit Type
                        </Typography>
                        <Chip
                          label={exitType}
                          size="small"
                          sx={{ 
                            bgcolor: exitType === 'SL' ? 'error.light' : 
                                     exitType === 'TP' ? 'success.light' : 'grey.500',
                            color: 'white',
                            fontWeight: 'bold'
                          }}
                        />
                      </Box>
                    </Box>
                  </Paper>
                )}

                <List sx={{ py: 0 }}>
                  {sortedTrades.map((trade, index) => {
                    const actionType = determineActionType(trade)
                    const isEntry = actionType === 'Entry'
                    const positionProgress = getPositionProgress(trade, entryMeta.entryQuantity)
                    const hasIndividualPnL = trade.realized_pnl_percent !== null && trade.realized_pnl_percent !== undefined
                    
                    // Get SL/TP values for this trade and previous trade - Task 10.2
                    const sltpValues = getSLTPValues(trade)
                    const { previousSL, previousTP } = getPreviousSLTP(sortedTrades, index)
                    const hasSLTP = sltpValues.currentSL !== null || sltpValues.currentTP !== null || 
                                    sltpValues.trailPrice !== null || sltpValues.trailOffset !== null

                    return (
                      <ListItem
                        key={trade.id}
                        onClick={(e) => handleTradeClick(e, trade)}
                        sx={{
                          position: 'relative',
                          flexDirection: 'column',
                          alignItems: 'stretch',
                          cursor: 'pointer',
                          '&:hover': { bgcolor: 'action.hover' },
                          '&::before': index < trades.length - 1 ? {
                            content: '""',
                            position: 'absolute',
                            left: 19,
                            top: 48,
                            bottom: -16,
                            width: 2,
                            bgcolor: 'divider'
                          } : {}
                        }}
                      >
                        <Box sx={{ display: 'flex', alignItems: 'flex-start' }}>
                          <Avatar
                            sx={{
                              bgcolor: 'background.paper',
                              border: 2,
                              borderColor: 'divider',
                              width: 40,
                              height: 40,
                              mr: 2
                            }}
                          >
                            {getActionIcon(actionType, direction)}
                          </Avatar>

                          <Box sx={{ flex: 1 }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5, flexWrap: 'wrap' }}>
                              <Chip
                                label={actionType}
                                size="small"
                                sx={{ fontWeight: 'bold', fontSize: '0.7rem' }}
                                color={
                                  actionType === 'Entry' ? 'primary' :
                                  actionType.startsWith('TP') ? 'success' :
                                  actionType.includes('SL') ? 'error' :
                                  'default'
                                }
                              />
                              {/* For entries, just show price. For exits, show action and quantity */}
                              {!isEntry && (
                                <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                                  {trade.action?.toUpperCase() || 'N/A'} {trade.quantity}
                                </Typography>
                              )}
                              <Chip
                                label={`@ ${trade.price || trade.metadata?.order_price || 'N/A'}`}
                                size="small"
                                variant="outlined"
                              />

                              {/* Individual P&L for exits - Task 7.3 */}
                              {!isEntry && hasIndividualPnL && (
                                <Chip
                                  icon={trade.realized_pnl_percent >= 0 ? 
                                    <TrendingUp sx={{ fontSize: '0.9rem' }} /> : 
                                    <TrendingDown sx={{ fontSize: '0.9rem' }} />
                                  }
                                  label={formatPnL(trade.realized_pnl_percent)}
                                  size="small"
                                  sx={{
                                    bgcolor: trade.realized_pnl_percent >= 0 ? 'success.main' : 'error.main',
                                    color: 'white',
                                    fontWeight: 'bold',
                                    fontSize: '0.7rem'
                                  }}
                                />
                              )}

                              {/* Absolute P&L if available */}
                              {!isEntry && trade.realized_pnl_absolute !== null && trade.realized_pnl_absolute !== undefined && (
                                <Typography 
                                  variant="caption" 
                                  sx={{ 
                                    color: trade.realized_pnl_absolute >= 0 ? 'success.main' : 'error.main',
                                    fontWeight: 'bold'
                                  }}
                                >
                                  (${trade.realized_pnl_absolute >= 0 ? '+' : ''}{trade.realized_pnl_absolute.toFixed(2)})
                                </Typography>
                              )}

                              {/* Leverage on entry */}
                              {isEntry && trade.leverage && (
                                <Chip
                                  label={`${trade.leverage}x`}
                                  size="small"
                                  variant="outlined"
                                  sx={{ fontSize: '0.7rem' }}
                                />
                              )}
                            </Box>

                            {/* SL/TP Change Indicator - Task 10.2 */}
                            {hasSLTP && (
                              <Box sx={{ mt: 0.5, mb: 0.5 }}>
                                <SLTPChangeIndicator
                                  currentSL={sltpValues.currentSL}
                                  previousSL={previousSL}
                                  currentTP={sltpValues.currentTP}
                                  previousTP={previousTP}
                                  tp1={sltpValues.tp1}
                                  tp2={sltpValues.tp2}
                                  tp3={sltpValues.tp3}
                                  tpCount={sltpValues.tpCount}
                                  trailPrice={sltpValues.trailPrice}
                                  trailOffset={sltpValues.trailOffset}
                                  compact={true}
                                  showLabels={true}
                                />
                              </Box>
                            )}

                            {/* Position Size After - Task 7.2 */}
                            {!isEntry && trade.position_size_after !== null && trade.position_size_after !== undefined && (
                              <Box sx={{ mt: 1, mb: 0.5 }}>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                                  <Typography variant="caption" color="text.secondary">
                                    Remaining Position:
                                  </Typography>
                                  <Typography variant="caption" sx={{ fontWeight: 'bold' }}>
                                    {trade.position_size_after.toFixed(3)}
                                  </Typography>
                                  {entryMeta.entryQuantity && (
                                    <Typography variant="caption" color="text.disabled">
                                      ({(100 - positionProgress).toFixed(1)}% left)
                                    </Typography>
                                  )}
                                </Box>
                                {/* Progress bar showing position reduction */}
                                <LinearProgress
                                  variant="determinate"
                                  value={positionProgress}
                                  sx={{
                                    height: 6,
                                    borderRadius: 3,
                                    bgcolor: 'grey.800',
                                    '& .MuiLinearProgress-bar': {
                                      bgcolor: positionProgress >= 100 ? 'success.main' : 'warning.main',
                                      borderRadius: 3
                                    }
                                  }}
                                />
                              </Box>
                            )}

                            <Typography variant="caption" color="text.secondary">
                              {format(new Date(trade.timestamp), 'MMM dd, yyyy HH:mm:ss')}
                              {' • '}
                              {trade.broker_order_id || 'No Order ID'}
                            </Typography>

                            {trade.error_message && (
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
                                <Typography variant="caption" color="error">
                                  ⚠️ {trade.error_message}
                                </Typography>
                                {(trade.status === 'parse_error' || trade.status === 'invalid') && (
                                  <Button
                                    size="small"
                                    variant="outlined"
                                    color="warning"
                                    onClick={(e) => handleReprocessSingle(e, trade)}
                                    disabled={reprocessing}
                                    sx={{ fontSize: '0.65rem', py: 0, minHeight: 20 }}
                                  >
                                    Reprocess
                                  </Button>
                                )}
                              </Box>
                            )}
                          </Box>
                        </Box>
                      </ListItem>
                    )
                  })}
                </List>
              </CardContent>
            </Collapse>
          </Card>
        )
      })}

      {/* Webhook Detail Modal */}
      <WebhookDetailModal
        webhook={selectedWebhook}
        open={modalOpen}
        onClose={handleCloseModal}
        onDelete={(id) => {
          handleCloseModal()
          if (onWebhookDeleted) onWebhookDeleted(id)
        }}
        onReprocess={handleWebhookUpdated}
      />
    </Stack>
  )
}

export default TradeGroupsView
