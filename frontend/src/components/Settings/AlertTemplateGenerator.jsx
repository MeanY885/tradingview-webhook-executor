import React, { useState } from 'react'
import {
  Box, Paper, Typography, TextField, Button, Radio,
  RadioGroup, FormControlLabel, FormControl, FormLabel,
  Alert, IconButton, Tabs, Tab
} from '@mui/material'
import { ContentCopy, CheckCircle } from '@mui/icons-material'
import { useAuth } from '../../context/AuthContext'

const AlertTemplateGenerator = () => {
  const { user } = useAuth()
  const [broker, setBroker] = useState('blofin')
  const [templateType, setTemplateType] = useState('strategy')
  const [format, setFormat] = useState('json')
  const [copiedUrl, setCopiedUrl] = useState(false)
  const [copiedMessage, setCopiedMessage] = useState(false)

  // Generate webhook URL
  const webhookUrl = user?.webhook_urls?.[broker] || ''

  // Generate message template based on selections
  const generateTemplate = () => {
    if (templateType === 'simple-buy') {
      return {
        json: `{
  "symbol": "{{ticker}}",
  "action": "buy",
  "order_type": "market",
  "quantity": 0.001
}`,
        text: `BUY {{ticker}} QTY:0.001`
      }
    } else if (templateType === 'simple-sell') {
      return {
        json: `{
  "symbol": "{{ticker}}",
  "action": "sell",
  "order_type": "market",
  "quantity": 0.001
}`,
        text: `SELL {{ticker}} QTY:0.001`
      }
    } else if (templateType === 'strategy') {
      return {
        json: `{
  "symbol": "{{ticker}}",
  "action": "{{strategy.order.action}}",
  "order_type": "market",
  "quantity": "{{strategy.order.contracts}}"
}`,
        text: `{{strategy.order.action}} {{ticker}} QTY:{{strategy.order.contracts}}`
      }
    } else if (templateType === 'with-sltp') {
      return {
        json: `{
  "symbol": "{{ticker}}",
  "action": "{{strategy.order.action}}",
  "order_type": "market",
  "quantity": "{{strategy.order.contracts}}",
  "stop_loss": 40000,
  "take_profit": 50000
}`,
        text: `{{strategy.order.action}} {{ticker}} QTY:{{strategy.order.contracts}} SL:40000 TP:50000`
      }
    }
  }

  const templates = generateTemplate()

  const copyToClipboard = (text, type) => {
    navigator.clipboard.writeText(text)
    if (type === 'url') {
      setCopiedUrl(true)
      setTimeout(() => setCopiedUrl(false), 2000)
    } else {
      setCopiedMessage(true)
      setTimeout(() => setCopiedMessage(false), 2000)
    }
  }

  return (
    <Paper sx={{ p: 3, mb: 3 }}>
      <Typography variant="h6" gutterBottom>
        TradingView Alert Setup
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Generate webhook URL and message templates for your TradingView alerts
      </Typography>

      {/* Step 1: Select Broker */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="subtitle2" gutterBottom>
          Step 1: Select Broker
        </Typography>
        <RadioGroup row value={broker} onChange={(e) => setBroker(e.target.value)}>
          <FormControlLabel value="blofin" control={<Radio />} label="Blofin (Crypto)" />
          <FormControlLabel value="oanda" control={<Radio />} label="Oanda (Forex)" />
        </RadioGroup>
      </Box>

      {/* Step 2: Copy Webhook URL */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="subtitle2" gutterBottom>
          Step 2: Copy Your Webhook URL
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <TextField
            fullWidth
            value={webhookUrl}
            InputProps={{ readOnly: true }}
            size="small"
          />
          <IconButton
            color={copiedUrl ? 'success' : 'primary'}
            onClick={() => copyToClipboard(webhookUrl, 'url')}
          >
            {copiedUrl ? <CheckCircle /> : <ContentCopy />}
          </IconButton>
        </Box>
        <Typography variant="caption" color="text.secondary">
          Paste this in TradingView → Notifications tab → Webhook URL
        </Typography>
      </Box>

      {/* Step 3: Choose Template Type */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="subtitle2" gutterBottom>
          Step 3: Choose Template Type
        </Typography>
        <RadioGroup value={templateType} onChange={(e) => setTemplateType(e.target.value)}>
          <FormControlLabel
            value="strategy"
            control={<Radio />}
            label="Strategy-Driven (uses {{strategy.order.action}})"
          />
          <FormControlLabel
            value="simple-buy"
            control={<Radio />}
            label="Simple Buy Order"
          />
          <FormControlLabel
            value="simple-sell"
            control={<Radio />}
            label="Simple Sell Order"
          />
          <FormControlLabel
            value="with-sltp"
            control={<Radio />}
            label="With Stop Loss & Take Profit"
          />
        </RadioGroup>
      </Box>

      {/* Step 4: Copy Message Template */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="subtitle2" gutterBottom>
          Step 4: Copy Message Template
        </Typography>

        <Tabs value={format} onChange={(e, v) => setFormat(v)} sx={{ mb: 2 }}>
          <Tab label="JSON Format (Recommended)" value="json" />
          <Tab label="Text Format" value="text" />
        </Tabs>

        <Box sx={{ position: 'relative' }}>
          <TextField
            fullWidth
            multiline
            rows={8}
            value={templates[format]}
            InputProps={{ readOnly: true }}
            sx={{ fontFamily: 'monospace', fontSize: '0.9em' }}
          />
          <IconButton
            color={copiedMessage ? 'success' : 'primary'}
            onClick={() => copyToClipboard(templates[format], 'message')}
            sx={{ position: 'absolute', top: 8, right: 8 }}
          >
            {copiedMessage ? <CheckCircle /> : <ContentCopy />}
          </IconButton>
        </Box>
        <Typography variant="caption" color="text.secondary">
          Paste this in TradingView → Message tab
        </Typography>
      </Box>

      {/* Instructions */}
      <Alert severity="info" sx={{ mt: 2 }}>
        <Typography variant="subtitle2" gutterBottom>
          How to use:
        </Typography>
        <ol style={{ margin: 0, paddingLeft: 20 }}>
          <li>Copy the Webhook URL above</li>
          <li>In TradingView, create an alert on your chart</li>
          <li>Go to "Notifications" tab → Enable "Webhook URL" → Paste URL</li>
          <li>Go to "Message" tab → Clear existing text → Paste template</li>
          <li>Adjust quantity, stop_loss, take_profit values as needed</li>
          <li>Create alert!</li>
        </ol>
      </Alert>
    </Paper>
  )
}

export default AlertTemplateGenerator
