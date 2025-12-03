import React from 'react'
import {
  Dialog, DialogTitle, DialogContent, DialogActions,
  Button, Box, Typography, Chip, Divider, Paper
} from '@mui/material'
import { format } from 'date-fns'

const WebhookDetailModal = ({ webhook, open, onClose }) => {
  if (!webhook) return null

  const renderJsonSection = (title, data) => {
    if (!data) return null

    return (
      <Box sx={{ mb: 3 }}>
        <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: 'bold', color: 'primary.main' }}>
          {title}
        </Typography>
        <Paper
          sx={{
            p: 2,
            bgcolor: 'grey.900',
            color: 'grey.100',
            fontFamily: 'monospace',
            fontSize: '0.85rem',
            overflowX: 'auto',
            maxHeight: '300px',
            overflowY: 'auto'
          }}
        >
          <pre style={{ margin: 0 }}>
            {typeof data === 'string' ? data : JSON.stringify(data, null, 2)}
          </pre>
        </Paper>
      </Box>
    )
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Typography variant="h6">Webhook Details</Typography>
          <Chip
            label={webhook.status?.toUpperCase()}
            size="small"
            color={
              webhook.status === 'success' || webhook.status === 'test_success' ? 'success' :
              webhook.status === 'failed' ? 'error' :
              webhook.status === 'invalid' || webhook.status === 'parse_error' ? 'warning' :
              'default'
            }
          />
        </Box>
      </DialogTitle>

      <DialogContent dividers>
        {/* Basic Info */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: 'bold' }}>
            Basic Information
          </Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: 1, ml: 2 }}>
            <Typography color="text.secondary">ID:</Typography>
            <Typography>{webhook.id}</Typography>

            <Typography color="text.secondary">Timestamp:</Typography>
            <Typography>
              {webhook.timestamp ? format(new Date(webhook.timestamp), 'MMM dd, yyyy HH:mm:ss') : 'N/A'}
            </Typography>

            <Typography color="text.secondary">Broker:</Typography>
            <Typography>{webhook.broker?.toUpperCase() || 'N/A'}</Typography>

            <Typography color="text.secondary">Symbol:</Typography>
            <Typography>{webhook.symbol || 'N/A'} {webhook.original_symbol && `(${webhook.original_symbol})`}</Typography>

            <Typography color="text.secondary">Action:</Typography>
            <Typography>{webhook.action?.toUpperCase() || 'N/A'}</Typography>

            <Typography color="text.secondary">Order Type:</Typography>
            <Typography>{webhook.order_type || 'N/A'}</Typography>

            <Typography color="text.secondary">Quantity:</Typography>
            <Typography>{webhook.quantity || 'N/A'}</Typography>

            {webhook.price && (
              <>
                <Typography color="text.secondary">Price:</Typography>
                <Typography>{webhook.price}</Typography>
              </>
            )}

            {webhook.leverage && (
              <>
                <Typography color="text.secondary">Leverage:</Typography>
                <Typography>{webhook.leverage}x</Typography>
              </>
            )}

            {webhook.stop_loss && (
              <>
                <Typography color="text.secondary">Stop Loss:</Typography>
                <Typography>{webhook.stop_loss}</Typography>
              </>
            )}

            {webhook.take_profit && (
              <>
                <Typography color="text.secondary">Take Profit:</Typography>
                <Typography>{webhook.take_profit}</Typography>
              </>
            )}

            {webhook.broker_order_id && (
              <>
                <Typography color="text.secondary">Broker Order ID:</Typography>
                <Typography sx={{ fontFamily: 'monospace', fontSize: '0.9em' }}>
                  {webhook.broker_order_id}
                </Typography>
              </>
            )}

            {webhook.client_order_id && (
              <>
                <Typography color="text.secondary">Client Order ID:</Typography>
                <Typography sx={{ fontFamily: 'monospace', fontSize: '0.9em' }}>
                  {webhook.client_order_id}
                </Typography>
              </>
            )}
          </Box>
        </Box>

        <Divider sx={{ my: 2 }} />

        {/* Error Message */}
        {webhook.error_message && (
          <>
            <Box sx={{ mb: 3 }}>
              <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: 'bold', color: 'error.main' }}>
                Error Message
              </Typography>
              <Paper sx={{ p: 2, bgcolor: 'error.light', color: 'error.contrastText' }}>
                <Typography sx={{ fontFamily: 'monospace', fontSize: '0.9em' }}>
                  {webhook.error_message}
                </Typography>
              </Paper>
            </Box>
            <Divider sx={{ my: 2 }} />
          </>
        )}

        {/* Metadata */}
        {webhook.metadata && Object.keys(webhook.metadata).length > 0 && (
          <>
            {renderJsonSection('TradingView Metadata', webhook.metadata)}
            <Divider sx={{ my: 2 }} />
          </>
        )}

        {/* Raw Payload */}
        {renderJsonSection('Raw Payload (Original JSON)', webhook.raw_payload || 'Not available')}
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  )
}

export default WebhookDetailModal
