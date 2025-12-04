import React, { useState, useEffect } from 'react'
import {
  Container, Paper, Typography, Tabs, Tab, Box,
  Button, TextField, Alert, CircularProgress, Grid
} from '@mui/material'
import api from '../services/api'
import AlertTemplateGenerator from '../components/Settings/AlertTemplateGenerator'
import IPWhitelistManager from '../components/Settings/IPWhitelistManager'
import PasswordChange from '../components/Settings/PasswordChange'

const Settings = () => {
  const [tab, setTab] = useState(0)
  const [credentials, setCredentials] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState(null)

  // Blofin form
  const [blofinData, setBlofinData] = useState({
    api_key: '',
    secret_key: '',
    passphrase: '',
    label: 'Main Account'
  })

  // Oanda form
  const [oandaData, setOandaData] = useState({
    api_key: '',
    account_id: '',
    label: 'Main Account'
  })

  useEffect(() => {
    fetchCredentials()
  }, [])

  const fetchCredentials = async () => {
    try {
      const response = await api.get('/api/credentials')
      setCredentials(response.data)
    } catch (error) {
      console.error('Failed to fetch credentials:', error)
    } finally {
      setLoading(false)
    }
  }

  const saveBlofinCredentials = async () => {
    setSaving(true)
    setMessage(null)

    try {
      await api.post('/api/credentials', {
        broker: 'blofin',
        ...blofinData
      })
      setMessage({ type: 'success', text: 'Blofin credentials saved successfully' })
      fetchCredentials()
      setBlofinData({ api_key: '', secret_key: '', passphrase: '', label: 'Main Account' })
    } catch (error) {
      setMessage({ type: 'error', text: error.response?.data?.error || 'Failed to save credentials' })
    } finally {
      setSaving(false)
    }
  }

  const saveOandaCredentials = async () => {
    setSaving(true)
    setMessage(null)

    try {
      await api.post('/api/credentials', {
        broker: 'oanda',
        ...oandaData
      })
      setMessage({ type: 'success', text: 'Oanda credentials saved successfully' })
      fetchCredentials()
      setOandaData({ api_key: '', account_id: '', label: 'Main Account' })
    } catch (error) {
      setMessage({ type: 'error', text: error.response?.data?.error || 'Failed to save credentials' })
    } finally {
      setSaving(false)
    }
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
      <Typography variant="h4" gutterBottom>
        Settings
      </Typography>

      {message && (
        <Alert severity={message.type} sx={{ mb: 2 }} onClose={() => setMessage(null)}>
          {message.text}
        </Alert>
      )}

      {/* TradingView Alert Template Generator */}
      <AlertTemplateGenerator />

      {/* IP Whitelist Manager */}
      <IPWhitelistManager />

      {/* Password Change */}
      <PasswordChange />

      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          API Credentials
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Add your broker API credentials to enable automated trading. All credentials are encrypted and stored securely.
        </Typography>

        <Tabs value={tab} onChange={(e, v) => setTab(v)} sx={{ mb: 3 }}>
          <Tab label="Blofin Credentials" />
          <Tab label="Oanda Credentials" />
        </Tabs>

        {tab === 0 && (
          <Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Enter your Blofin API credentials. You can create API keys from your Blofin account settings.
            </Typography>

            <Grid container spacing={2}>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="API Key"
                  value={blofinData.api_key}
                  onChange={(e) => setBlofinData({ ...blofinData, api_key: e.target.value })}
                />
              </Grid>

              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="Secret Key"
                  type="password"
                  value={blofinData.secret_key}
                  onChange={(e) => setBlofinData({ ...blofinData, secret_key: e.target.value })}
                />
              </Grid>

              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="Passphrase"
                  type="password"
                  value={blofinData.passphrase}
                  onChange={(e) => setBlofinData({ ...blofinData, passphrase: e.target.value })}
                />
              </Grid>

              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="Label (optional)"
                  value={blofinData.label}
                  onChange={(e) => setBlofinData({ ...blofinData, label: e.target.value })}
                  helperText="Give this credential set a friendly name"
                />
              </Grid>

              <Grid item xs={12}>
                <Button
                  variant="contained"
                  onClick={saveBlofinCredentials}
                  disabled={saving || !blofinData.api_key || !blofinData.secret_key || !blofinData.passphrase}
                >
                  {saving ? <CircularProgress size={24} /> : 'Save Blofin Credentials'}
                </Button>
              </Grid>
            </Grid>
          </Box>
        )}

        {tab === 1 && (
          <Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Enter your Oanda API credentials. You can generate a Personal Access Token from your Oanda account.
            </Typography>

            <Grid container spacing={2}>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="API Key (Personal Access Token)"
                  value={oandaData.api_key}
                  onChange={(e) => setOandaData({ ...oandaData, api_key: e.target.value })}
                />
              </Grid>

              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="Account ID"
                  value={oandaData.account_id}
                  onChange={(e) => setOandaData({ ...oandaData, account_id: e.target.value })}
                  helperText="Your Oanda account number (e.g., 001-001-1234567-001)"
                />
              </Grid>

              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="Label (optional)"
                  value={oandaData.label}
                  onChange={(e) => setOandaData({ ...oandaData, label: e.target.value })}
                  helperText="Give this credential set a friendly name"
                />
              </Grid>

              <Grid item xs={12}>
                <Button
                  variant="contained"
                  onClick={saveOandaCredentials}
                  disabled={saving || !oandaData.api_key || !oandaData.account_id}
                >
                  {saving ? <CircularProgress size={24} /> : 'Save Oanda Credentials'}
                </Button>
              </Grid>
            </Grid>
          </Box>
        )}
      </Paper>

      {/* Show existing credentials */}
      <Paper sx={{ p: 3, mt: 3 }}>
        <Typography variant="h6" gutterBottom>
          Saved Credentials
        </Typography>
        {credentials.length === 0 ? (
          <Typography color="text.secondary">No credentials saved yet.</Typography>
        ) : (
          <Box>
            {credentials.map(cred => (
              <Box key={cred.id} sx={{ mb: 2, p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
                <Typography variant="subtitle1">
                  {cred.broker.toUpperCase()} - {cred.label}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Added: {new Date(cred.created_at).toLocaleDateString()}
                  {' | '}
                  Status: {cred.is_active ? 'Active' : 'Inactive'}
                </Typography>
              </Box>
            ))}
          </Box>
        )}
      </Paper>
    </Box>
  )
}

export default Settings
