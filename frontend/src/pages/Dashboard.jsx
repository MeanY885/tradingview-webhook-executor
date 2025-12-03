import React, { useState, useEffect } from 'react'
import { Grid, Paper, Typography, Box, ToggleButtonGroup, ToggleButton } from '@mui/material'
import { ViewList, ViewModule } from '@mui/icons-material'
import { getSocket } from '../services/socket'
import api from '../services/api'
import RealTimeWebhookFeed from '../components/Dashboard/RealTimeWebhookFeed'
import TradeGroupsView from '../components/Dashboard/TradeGroupsView'
import StatisticsCards from '../components/Dashboard/StatisticsCards'

const Dashboard = () => {
  const [recentWebhooks, setRecentWebhooks] = useState([])
  const [stats, setStats] = useState({})
  const [loading, setLoading] = useState(true)
  const [viewMode, setViewMode] = useState('grouped') // 'list' or 'grouped'

  useEffect(() => {
    // Fetch initial webhook logs
    fetchRecentLogs()
    fetchStats()

    // Listen for real-time webhook events
    const socket = getSocket()
    if (socket) {
      socket.on('webhook_received', (data) => {
        console.log('Webhook received:', data)
        // Refetch logs to get proper grouping
        fetchRecentLogs()
        // Refresh stats
        fetchStats()
      })

      socket.on('connection_status', (data) => {
        console.log('WebSocket connected:', data)
      })
    }

    return () => {
      if (socket) {
        socket.off('webhook_received')
        socket.off('connection_status')
      }
    }
  }, [])

  const fetchRecentLogs = async () => {
    try {
      const response = await api.get('/api/webhook-logs?per_page=20')
      setRecentWebhooks(response.data.logs)
    } catch (error) {
      console.error('Failed to fetch logs:', error)
    } finally {
      setLoading(false)
    }
  }

  const fetchStats = async () => {
    try {
      const response = await api.get('/api/webhook-logs/stats')
      setStats(response.data.by_status || {})
    } catch (error) {
      console.error('Failed to fetch stats:', error)
    }
  }

  const handleWebhookDeleted = (webhookId) => {
    // Remove the webhook from the local state
    setRecentWebhooks(prev => prev.filter(webhook => webhook.id !== webhookId))
    // Refresh stats
    fetchStats()
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Dashboard
      </Typography>

      <Grid container spacing={3}>
        <Grid item xs={12}>
          <StatisticsCards stats={stats} />
        </Grid>

        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6">
                {viewMode === 'grouped' ? 'Trade Groups' : 'Real-Time Webhook Feed'}
              </Typography>
              <ToggleButtonGroup
                value={viewMode}
                exclusive
                onChange={(e, newMode) => newMode && setViewMode(newMode)}
                size="small"
              >
                <ToggleButton value="grouped">
                  <ViewModule sx={{ mr: 1 }} fontSize="small" />
                  Grouped
                </ToggleButton>
                <ToggleButton value="list">
                  <ViewList sx={{ mr: 1 }} fontSize="small" />
                  List
                </ToggleButton>
              </ToggleButtonGroup>
            </Box>

            {viewMode === 'grouped' ? (
              <TradeGroupsView
                webhooks={recentWebhooks}
                onWebhookDeleted={handleWebhookDeleted}
              />
            ) : (
              <RealTimeWebhookFeed
                webhooks={recentWebhooks}
                loading={loading}
                onWebhookDeleted={handleWebhookDeleted}
              />
            )}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  )
}

export default Dashboard
