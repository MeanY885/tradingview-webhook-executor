import React, { useState } from 'react'
import {
  Box, Card, CardContent, Collapse, Typography, IconButton,
  Chip, Divider, List, ListItem, Avatar, Tooltip, Stack
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
  Error as ErrorIcon,
  Delete as DeleteIcon
} from '@mui/icons-material'
import { format } from 'date-fns'
import api from '../../services/api'

const TradeGroupsView = ({ webhooks, onWebhookDeleted }) => {
  const [expandedGroups, setExpandedGroups] = useState({})

  // Group webhooks by trade_group_id
  const groupedTrades = webhooks.reduce((groups, webhook) => {
    const groupId = webhook.trade_group_id || `ungrouped-${webhook.id}`
    if (!groups[groupId]) {
      groups[groupId] = []
    }
    groups[groupId].push(webhook)
    return groups
  }, {})

  // Sort groups by most recent first
  const sortedGroups = Object.entries(groupedTrades).sort((a, b) => {
    const aTime = new Date(a[1][0].timestamp).getTime()
    const bTime = new Date(b[1][0].timestamp).getTime()
    return bTime - aTime
  })

  const toggleGroup = (groupId) => {
    setExpandedGroups(prev => ({
      ...prev,
      [groupId]: !prev[groupId]
    }))
  }

  const determineActionType = (webhook) => {
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
    if (alertMessage.includes('reduce')) return 'Reduce'
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

  const calculatePnL = (trades) => {
    const sortedTrades = [...trades].sort((a, b) =>
      new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    )

    const entry = sortedTrades.find(t => t.action === 'buy')
    const exits = sortedTrades.filter(t => t.action === 'sell')

    if (!entry || exits.length === 0) return null

    const entryPrice = entry.price || entry.metadata?.order_price
    let totalPnL = 0
    let totalQuantity = 0

    exits.forEach(exit => {
      const exitPrice = exit.price || exit.metadata?.order_price
      const quantity = exit.quantity
      if (entryPrice && exitPrice && quantity) {
        const pnl = ((exitPrice - entryPrice) / entryPrice) * 100
        totalPnL += pnl * quantity
        totalQuantity += quantity
      }
    })

    return totalQuantity > 0 ? totalPnL / totalQuantity : 0
  }

  const getTradeStatus = (trades) => {
    const hasFlat = trades.some(t => t.metadata?.market_position === 'flat')
    const allSuccess = trades.every(t => t.status === 'test_success' || t.status === 'success')

    if (hasFlat) return 'CLOSED'
    if (allSuccess) return 'ACTIVE'
    return 'PENDING'
  }

  const handleDeleteGroup = async (e, groupId, trades) => {
    e.stopPropagation()

    if (!window.confirm(`Delete entire trade group with ${trades.length} entries?`)) {
      return
    }

    try {
      // Delete all webhooks in the group
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

  if (sortedGroups.length === 0) {
    return (
      <Typography color="text.secondary" align="center" sx={{ py: 4 }}>
        No trades yet. Waiting for TradingView alerts...
      </Typography>
    )
  }

  return (
    <Stack spacing={2}>
      {sortedGroups.map(([groupId, trades]) => {
        const isExpanded = expandedGroups[groupId]
        const direction = trades[0]?.trade_direction
        const symbol = trades[0]?.symbol
        const pnl = calculatePnL(trades)
        const status = getTradeStatus(trades)
        const entryTrade = [...trades].sort((a, b) =>
          new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
        )[0]
        const latestTrade = [...trades].sort((a, b) =>
          new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
        )[0]

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
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flex: 1 }}>
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

                  {/* Entry → Exit */}
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Chip
                      label={`Entry: ${entryTrade?.price || entryTrade?.metadata?.order_price || 'N/A'}`}
                      size="small"
                      variant="outlined"
                    />
                    <Typography color="text.disabled">→</Typography>
                    <Chip
                      label={`Exit: ${latestTrade?.price || latestTrade?.metadata?.order_price || 'N/A'}`}
                      size="small"
                      variant="outlined"
                    />
                  </Box>

                  {/* P&L */}
                  {pnl !== null && (
                    <Chip
                      icon={pnl >= 0 ? <TrendingUp fontSize="small" /> : <TrendingDown fontSize="small" />}
                      label={`${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}%`}
                      size="small"
                      sx={{
                        bgcolor: pnl >= 0 ? 'success.dark' : 'error.dark',
                        color: 'white',
                        fontWeight: 'bold'
                      }}
                    />
                  )}

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
                <List sx={{ py: 0 }}>
                  {[...trades]
                    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
                    .map((trade, index) => {
                      const actionType = determineActionType(trade)
                      return (
                        <ListItem
                          key={trade.id}
                          sx={{
                            position: 'relative',
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
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
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
                              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                                {trade.action.toUpperCase()} {trade.quantity}
                              </Typography>
                              <Chip
                                label={`@ ${trade.price || trade.metadata?.order_price || 'N/A'}`}
                                size="small"
                                variant="outlined"
                              />
                              {trade.leverage && (
                                <Chip
                                  label={`${trade.leverage}x`}
                                  size="small"
                                  variant="outlined"
                                  sx={{ fontSize: '0.7rem' }}
                                />
                              )}
                            </Box>

                            <Typography variant="caption" color="text.secondary">
                              {format(new Date(trade.timestamp), 'MMM dd, yyyy HH:mm:ss')}
                              {' • '}
                              {trade.broker_order_id || 'No Order ID'}
                            </Typography>

                            {trade.error_message && (
                              <Typography variant="caption" color="error" display="block" sx={{ mt: 0.5 }}>
                                ⚠️ {trade.error_message}
                              </Typography>
                            )}
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
    </Stack>
  )
}

export default TradeGroupsView
