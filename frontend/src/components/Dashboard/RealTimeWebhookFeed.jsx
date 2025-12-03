import React, { useState } from 'react'
import {
  List, ListItem, ListItemText, Chip, Box,
  Typography, CircularProgress
} from '@mui/material'
import { CheckCircle, Error, Pending } from '@mui/icons-material'
import { format } from 'date-fns'
import WebhookDetailModal from './WebhookDetailModal'

const StatusIcon = ({ status }) => {
  switch (status) {
    case 'success':
      return <CheckCircle color="success" />
    case 'failed':
      return <Error color="error" />
    case 'invalid':
      return <Error color="warning" />
    default:
      return <Pending color="info" />
  }
}

const RealTimeWebhookFeed = ({ webhooks, loading, onWebhookDeleted }) => {
  const [selectedWebhook, setSelectedWebhook] = useState(null)
  const [modalOpen, setModalOpen] = useState(false)

  const handleWebhookClick = (webhook) => {
    setSelectedWebhook(webhook)
    setModalOpen(true)
  }

  const handleCloseModal = () => {
    setModalOpen(false)
    setSelectedWebhook(null)
  }

  const handleDelete = (webhookId) => {
    if (onWebhookDeleted) {
      onWebhookDeleted(webhookId)
    }
  }

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress />
      </Box>
    )
  }

  if (webhooks.length === 0) {
    return (
      <Typography color="text.secondary" align="center" sx={{ py: 4 }}>
        No webhooks received yet. Waiting for TradingView alerts...
      </Typography>
    )
  }

  return (
    <>
      <List>
        {webhooks.map((webhook) => (
          <ListItem
            key={webhook.id}
            divider
            button
            onClick={() => handleWebhookClick(webhook)}
            sx={{
              animation: 'fadeIn 0.5s',
              cursor: 'pointer',
              '&:hover': {
                bgcolor: 'action.hover'
              },
              '@keyframes fadeIn': {
                from: { opacity: 0, transform: 'translateY(-10px)' },
                to: { opacity: 1, transform: 'translateY(0)' }
              }
            }}
          >
          <Box sx={{ display: 'flex', alignItems: 'center', width: '100%', gap: 2 }}>
            <StatusIcon status={webhook.status} />
            <ListItemText
              primary={
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                  <Chip
                    label={webhook.broker?.toUpperCase() || 'UNKNOWN'}
                    size="small"
                    color={webhook.broker === 'blofin' ? 'primary' : 'secondary'}
                  />
                  {webhook.trade_direction && (
                    <Chip
                      label={webhook.trade_direction.toUpperCase()}
                      size="small"
                      sx={{
                        bgcolor: webhook.trade_direction === 'long' ? 'success.main' : 'error.main',
                        color: 'white',
                        fontWeight: 'bold'
                      }}
                    />
                  )}
                  <Typography variant="body1" component="span">
                    {webhook.action?.toUpperCase()} {webhook.quantity} {webhook.symbol}
                  </Typography>
                  <Chip
                    label={webhook.order_type}
                    size="small"
                    variant="outlined"
                  />
                  {webhook.price && (
                    <Typography variant="body2" color="text.secondary" component="span">
                      @ {webhook.price}
                    </Typography>
                  )}
                </Box>
              }
              secondary={
                <>
                  {webhook.trade_group_id && (
                    <Typography variant="caption" sx={{ fontFamily: 'monospace', color: 'text.disabled' }} component="div">
                      Group: {webhook.trade_group_id}
                    </Typography>
                  )}
                  <Typography variant="body2" color="text.secondary" component="span">
                    Status: {webhook.status}
                  </Typography>
                  {webhook.broker_order_id && (
                    <Typography variant="body2" color="text.secondary" component="span">
                      {' | Order ID: '}
                      {webhook.broker_order_id}
                    </Typography>
                  )}
                  {webhook.timestamp && (
                    <Typography variant="body2" color="text.secondary" component="span">
                      {' | '}
                      {format(new Date(webhook.timestamp), 'MMM dd, yyyy HH:mm:ss')}
                    </Typography>
                  )}
                  {webhook.error_message && (
                    <Typography color="error" variant="caption" display="block">
                      Error: {webhook.error_message}
                    </Typography>
                  )}
                </>
              }
            />
          </Box>
        </ListItem>
      ))}
    </List>

    <WebhookDetailModal
      webhook={selectedWebhook}
      open={modalOpen}
      onClose={handleCloseModal}
      onDelete={handleDelete}
    />
  </>
  )
}

export default RealTimeWebhookFeed
