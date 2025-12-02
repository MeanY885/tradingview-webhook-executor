import React, { useState, useEffect } from 'react'
import {
  Paper,
  Typography,
  Switch,
  FormControlLabel,
  TextField,
  Button,
  IconButton,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Alert,
  Box,
  Chip,
  CircularProgress
} from '@mui/material'
import { Delete as DeleteIcon, Add as AddIcon } from '@mui/icons-material'
import api from '../../services/api'

const IPWhitelistManager = () => {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [enabled, setEnabled] = useState(false)
  const [whitelist, setWhitelist] = useState([])
  const [tradingviewIps, setTradingviewIps] = useState([])
  const [newIp, setNewIp] = useState('')
  const [message, setMessage] = useState(null)

  useEffect(() => {
    fetchWhitelist()
  }, [])

  const fetchWhitelist = async () => {
    try {
      const response = await api.get('/api/auth/webhook-ip-whitelist')
      setEnabled(response.data.enabled)
      setWhitelist(response.data.whitelist || [])
      setTradingviewIps(response.data.tradingview_ips || [])
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to load IP whitelist settings' })
    } finally {
      setLoading(false)
    }
  }

  const handleToggleEnabled = async (event) => {
    const newEnabled = event.target.checked
    setSaving(true)
    setMessage(null)

    try {
      await api.put('/api/auth/webhook-ip-whitelist', { enabled: newEnabled })
      setEnabled(newEnabled)
      setMessage({
        type: 'success',
        text: newEnabled
          ? 'IP whitelist enabled - only listed IPs can send webhooks'
          : 'IP whitelist disabled - all IPs allowed'
      })
    } catch (error) {
      setMessage({ type: 'error', text: error.response?.data?.error || 'Failed to update setting' })
    } finally {
      setSaving(false)
    }
  }

  const handleAddIp = async () => {
    if (!newIp.trim()) return

    const updatedWhitelist = [...whitelist, newIp.trim()]
    setSaving(true)
    setMessage(null)

    try {
      await api.put('/api/auth/webhook-ip-whitelist', { whitelist: updatedWhitelist })
      setWhitelist(updatedWhitelist)
      setNewIp('')
      setMessage({ type: 'success', text: 'IP address added successfully' })
    } catch (error) {
      setMessage({ type: 'error', text: error.response?.data?.error || 'Failed to add IP address' })
    } finally {
      setSaving(false)
    }
  }

  const handleRemoveIp = async (ipToRemove) => {
    const updatedWhitelist = whitelist.filter(ip => ip !== ipToRemove)
    setSaving(true)
    setMessage(null)

    try {
      await api.put('/api/auth/webhook-ip-whitelist', { whitelist: updatedWhitelist })
      setWhitelist(updatedWhitelist)
      setMessage({ type: 'success', text: 'IP address removed successfully' })
    } catch (error) {
      setMessage({ type: 'error', text: error.response?.data?.error || 'Failed to remove IP address' })
    } finally {
      setSaving(false)
    }
  }

  const handleAddTradingViewIps = async () => {
    const updatedWhitelist = [...new Set([...whitelist, ...tradingviewIps])]
    setSaving(true)
    setMessage(null)

    try {
      await api.put('/api/auth/webhook-ip-whitelist', { whitelist: updatedWhitelist })
      setWhitelist(updatedWhitelist)
      setMessage({ type: 'success', text: 'TradingView IPs added successfully' })
    } catch (error) {
      setMessage({ type: 'error', text: error.response?.data?.error || 'Failed to add TradingView IPs' })
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <CircularProgress />
  }

  return (
    <Paper sx={{ p: 3, mb: 3 }}>
      <Typography variant="h6" gutterBottom>
        Webhook IP Whitelist
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Restrict webhook access to specific IP addresses. When enabled, only webhooks from whitelisted IPs will be processed.
      </Typography>

      {message && (
        <Alert severity={message.type} sx={{ mb: 2 }} onClose={() => setMessage(null)}>
          {message.text}
        </Alert>
      )}

      {/* Enable/Disable Toggle */}
      <FormControlLabel
        control={
          <Switch
            checked={enabled}
            onChange={handleToggleEnabled}
            disabled={saving}
          />
        }
        label={enabled ? 'IP Whitelist Enabled' : 'IP Whitelist Disabled'}
        sx={{ mb: 3 }}
      />

      {/* Quick Add TradingView IPs */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="subtitle2" gutterBottom>
          TradingView Official Webhook IPs
        </Typography>
        <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
          These are TradingView's official webhook IP addresses
        </Typography>
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
          {tradingviewIps.map((ip) => (
            <Chip
              key={ip}
              label={ip}
              size="small"
              color={whitelist.includes(ip) ? 'success' : 'default'}
              variant={whitelist.includes(ip) ? 'filled' : 'outlined'}
            />
          ))}
        </Box>
        <Button
          variant="outlined"
          size="small"
          onClick={handleAddTradingViewIps}
          disabled={saving || tradingviewIps.every(ip => whitelist.includes(ip))}
        >
          {tradingviewIps.every(ip => whitelist.includes(ip))
            ? 'All TradingView IPs Added'
            : 'Add All TradingView IPs'}
        </Button>
      </Box>

      {/* Add Custom IP */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="subtitle2" gutterBottom>
          Add Custom IP Address
        </Typography>
        <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
          Supports both single IPs (e.g., 192.168.1.1) and CIDR notation (e.g., 192.168.1.0/24)
        </Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <TextField
            fullWidth
            size="small"
            placeholder="Enter IP address or CIDR"
            value={newIp}
            onChange={(e) => setNewIp(e.target.value)}
            onKeyPress={(e) => {
              if (e.key === 'Enter') {
                handleAddIp()
              }
            }}
            disabled={saving}
          />
          <IconButton
            color="primary"
            onClick={handleAddIp}
            disabled={!newIp.trim() || saving}
          >
            <AddIcon />
          </IconButton>
        </Box>
      </Box>

      {/* Current Whitelist */}
      <Box>
        <Typography variant="subtitle2" gutterBottom>
          Whitelisted IP Addresses ({whitelist.length})
        </Typography>
        {whitelist.length === 0 ? (
          <Alert severity="warning" sx={{ mt: 1 }}>
            No IP addresses whitelisted. {enabled ? 'All webhook requests will be blocked!' : 'Add IPs before enabling the whitelist.'}
          </Alert>
        ) : (
          <List dense>
            {whitelist.map((ip, index) => (
              <ListItem
                key={index}
                sx={{
                  border: '1px solid',
                  borderColor: 'divider',
                  borderRadius: 1,
                  mb: 1
                }}
              >
                <ListItemText
                  primary={ip}
                  secondary={tradingviewIps.includes(ip) ? 'TradingView Official IP' : 'Custom IP'}
                />
                <ListItemSecondaryAction>
                  <IconButton
                    edge="end"
                    onClick={() => handleRemoveIp(ip)}
                    disabled={saving}
                    size="small"
                  >
                    <DeleteIcon />
                  </IconButton>
                </ListItemSecondaryAction>
              </ListItem>
            ))}
          </List>
        )}
      </Box>

      {/* Warning */}
      {enabled && whitelist.length === 0 && (
        <Alert severity="error" sx={{ mt: 2 }}>
          ⚠️ Warning: IP whitelist is enabled but no IPs are whitelisted. All webhook requests will be rejected!
        </Alert>
      )}
    </Paper>
  )
}

export default IPWhitelistManager
