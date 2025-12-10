import { useState, useEffect } from 'react'
import {
  Box, Paper, Typography, Button, TextField, Alert, CircularProgress,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  IconButton, Dialog, DialogTitle, DialogContent, DialogActions,
  FormControl, InputLabel, Select, MenuItem, Chip, Grid, Tooltip
} from '@mui/material'
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  TrendingUp as TrendingUpIcon
} from '@mui/icons-material'
import api from '../services/api'

const SymbolConfigs = () => {
  const [configs, setConfigs] = useState([])
  const [suggestions, setSuggestions] = useState([])
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingConfig, setEditingConfig] = useState(null)
  const [saving, setSaving] = useState(false)

  // Form state
  const [formData, setFormData] = useState({
    symbol: '',
    broker: 'oanda',
    tp_count: 1,
    sl_count: 1,
    display_name: ''
  })

  useEffect(() => {
    fetchConfigs()
    fetchSuggestions()
  }, [])

  const fetchConfigs = async () => {
    try {
      const response = await api.get('/api/symbol-configs/')
      setConfigs(response.data.configs || [])
    } catch (error) {
      console.error('Failed to fetch configs:', error)
      setMessage({ type: 'error', text: 'Failed to load symbol configurations' })
    } finally {
      setLoading(false)
    }
  }

  const fetchSuggestions = async () => {
    try {
      const response = await api.get('/api/symbol-configs/suggestions')
      setSuggestions(response.data.suggestions || [])
    } catch (error) {
      console.error('Failed to fetch suggestions:', error)
    }
  }

  const handleOpenDialog = (config = null) => {
    if (config) {
      setEditingConfig(config)
      setFormData({
        symbol: config.symbol,
        broker: config.broker,
        tp_count: config.tp_count,
        sl_count: config.sl_count,
        display_name: config.display_name || ''
      })
    } else {
      setEditingConfig(null)
      setFormData({
        symbol: '',
        broker: 'oanda',
        tp_count: 1,
        sl_count: 1,
        display_name: ''
      })
    }
    setDialogOpen(true)
  }

  const handleCloseDialog = () => {
    setDialogOpen(false)
    setEditingConfig(null)
  }

  const handleSave = async () => {
    setSaving(true)
    setMessage(null)

    try {
      if (editingConfig) {
        await api.put(`/api/symbol-configs/${editingConfig.id}`, {
          tp_count: formData.tp_count,
          sl_count: formData.sl_count,
          display_name: formData.display_name
        })
        setMessage({ type: 'success', text: 'Configuration updated successfully' })
      } else {
        await api.post('/api/symbol-configs/', formData)
        setMessage({ type: 'success', text: 'Configuration created successfully' })
      }
      fetchConfigs()
      fetchSuggestions()  // Refresh suggestions after adding
      handleCloseDialog()
    } catch (error) {
      setMessage({ 
        type: 'error', 
        text: error.response?.data?.error || 'Failed to save configuration' 
      })
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (config) => {
    if (!window.confirm(`Delete configuration for ${config.symbol}?`)) return

    try {
      await api.delete(`/api/symbol-configs/${config.id}`)
      setMessage({ type: 'success', text: 'Configuration deleted' })
      fetchConfigs()
      fetchSuggestions()  // Refresh suggestions after delete
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to delete configuration' })
    }
  }

  const getBrokerColor = (broker) => {
    return broker === 'oanda' ? 'primary' : 'secondary'
  }

  const getTPChips = (count) => {
    const chips = []
    for (let i = 1; i <= 3; i++) {
      chips.push(
        <Chip
          key={`tp${i}`}
          label={`TP${i}`}
          size="small"
          color={i <= count ? 'success' : 'default'}
          variant={i <= count ? 'filled' : 'outlined'}
          sx={{ mr: 0.5 }}
        />
      )
    }
    return chips
  }

  const getSLChips = (count) => {
    const chips = []
    for (let i = 1; i <= 3; i++) {
      chips.push(
        <Chip
          key={`sl${i}`}
          label={`SL${i}`}
          size="small"
          color={i <= count ? 'error' : 'default'}
          variant={i <= count ? 'filled' : 'outlined'}
          sx={{ mr: 0.5 }}
        />
      )
    }
    return chips
  }

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress />
      </Box>
    )
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" gutterBottom>
            Symbol Configuration
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Configure TP and SL levels for each trading symbol. This determines when a trade is considered closed.
          </Typography>
        </Box>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => handleOpenDialog()}
        >
          Add Symbol
        </Button>
      </Box>

      {message && (
        <Alert severity={message.type} sx={{ mb: 2 }} onClose={() => setMessage(null)}>
          {message.text}
        </Alert>
      )}

      <Paper sx={{ p: 2 }}>
        {configs.length === 0 ? (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <TrendingUpIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
            <Typography variant="h6" color="text.secondary">
              No symbol configurations yet
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Add your first symbol to configure TP/SL levels
            </Typography>
            <Button variant="outlined" startIcon={<AddIcon />} onClick={() => handleOpenDialog()}>
              Add Symbol
            </Button>
          </Box>
        ) : (
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Symbol</TableCell>
                  <TableCell>Broker</TableCell>
                  <TableCell>Take Profit Levels</TableCell>
                  <TableCell>Stop Loss Levels</TableCell>
                  <TableCell>Closes On</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {configs.map((config) => (
                  <TableRow key={config.id} hover>
                    <TableCell>
                      <Typography variant="subtitle2">
                        {config.symbol}
                      </Typography>
                      {config.display_name && (
                        <Typography variant="caption" color="text.secondary">
                          {config.display_name}
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell>
                      <Chip 
                        label={config.broker.toUpperCase()} 
                        size="small" 
                        color={getBrokerColor(config.broker)}
                      />
                    </TableCell>
                    <TableCell>
                      {getTPChips(config.tp_count)}
                    </TableCell>
                    <TableCell>
                      {getSLChips(config.sl_count)}
                    </TableCell>
                    <TableCell>
                      <Tooltip title="Trade closes when this level is hit">
                        <Box>
                          <Chip 
                            label={`TP${config.tp_count}`} 
                            size="small" 
                            color="success" 
                            sx={{ mr: 0.5 }}
                          />
                          <Typography variant="caption" color="text.secondary">or</Typography>
                          <Chip 
                            label={config.sl_count > 1 ? `SL${config.sl_count}` : 'SL'} 
                            size="small" 
                            color="error" 
                            sx={{ ml: 0.5 }}
                          />
                        </Box>
                      </Tooltip>
                    </TableCell>
                    <TableCell align="right">
                      <IconButton size="small" onClick={() => handleOpenDialog(config)}>
                        <EditIcon fontSize="small" />
                      </IconButton>
                      <IconButton size="small" color="error" onClick={() => handleDelete(config)}>
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>

      {/* Quick Add from Trade History */}
      {suggestions.length > 0 && (
        <Paper sx={{ p: 2, mt: 2 }}>
          <Typography variant="subtitle2" gutterBottom>
            Symbols from your trade history (not yet configured):
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 1 }}>
            {suggestions.map(({ symbol, broker }) => (
              <Chip
                key={`${symbol}-${broker}`}
                label={`${symbol} (${broker})`}
                size="small"
                variant="outlined"
                color={broker === 'oanda' ? 'primary' : 'secondary'}
                onClick={() => {
                  setFormData({ symbol, broker, tp_count: 1, sl_count: 1, display_name: '' })
                  setEditingConfig(null)
                  setDialogOpen(true)
                }}
              />
            ))}
          </Box>
        </Paper>
      )}

      {/* Info Box */}
      <Paper sx={{ p: 2, mt: 2, bgcolor: 'background.default' }}>
        <Typography variant="subtitle2" gutterBottom>
          How it works:
        </Typography>
        <Typography variant="body2" color="text.secondary">
          • <strong>TP Count = 1:</strong> Trade closes when TP1 is hit<br />
          • <strong>TP Count = 2:</strong> TP1 is partial, trade closes on TP2<br />
          • <strong>TP Count = 3:</strong> TP1 & TP2 are partial, trade closes on TP3<br />
          • <strong>SL Count:</strong> Same logic applies for stop losses<br />
          • Symbols without a config default to TP1/SL1 (single level)
        </Typography>
      </Paper>

      {/* Add/Edit Dialog */}
      <Dialog open={dialogOpen} onClose={handleCloseDialog} maxWidth="sm" fullWidth>
        <DialogTitle>
          {editingConfig ? 'Edit Symbol Configuration' : 'Add Symbol Configuration'}
        </DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Symbol"
                value={formData.symbol}
                onChange={(e) => setFormData({ ...formData, symbol: e.target.value.toUpperCase() })}
                disabled={!!editingConfig}
                placeholder="e.g., EUR_USD"
                helperText="Use broker format (e.g., EUR_USD for Oanda)"
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth disabled={!!editingConfig}>
                <InputLabel>Broker</InputLabel>
                <Select
                  value={formData.broker}
                  label="Broker"
                  onChange={(e) => setFormData({ ...formData, broker: e.target.value })}
                >
                  <MenuItem value="oanda">Oanda (Forex)</MenuItem>
                  <MenuItem value="blofin">Blofin (Crypto)</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Take Profit Levels</InputLabel>
                <Select
                  value={formData.tp_count}
                  label="Take Profit Levels"
                  onChange={(e) => setFormData({ ...formData, tp_count: e.target.value })}
                >
                  <MenuItem value={1}>1 TP (TP1 closes trade)</MenuItem>
                  <MenuItem value={2}>2 TPs (TP2 closes trade)</MenuItem>
                  <MenuItem value={3}>3 TPs (TP3 closes trade)</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Stop Loss Levels</InputLabel>
                <Select
                  value={formData.sl_count}
                  label="Stop Loss Levels"
                  onChange={(e) => setFormData({ ...formData, sl_count: e.target.value })}
                >
                  <MenuItem value={1}>1 SL (SL closes trade)</MenuItem>
                  <MenuItem value={2}>2 SLs (SL2 closes trade)</MenuItem>
                  <MenuItem value={3}>3 SLs (SL3 closes trade)</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Display Name (optional)"
                value={formData.display_name}
                onChange={(e) => setFormData({ ...formData, display_name: e.target.value })}
                placeholder="e.g., Euro/US Dollar"
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Cancel</Button>
          <Button 
            variant="contained" 
            onClick={handleSave}
            disabled={saving || !formData.symbol}
          >
            {saving ? <CircularProgress size={24} /> : (editingConfig ? 'Update' : 'Create')}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}

export default SymbolConfigs
