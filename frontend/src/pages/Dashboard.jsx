import React, { useState, useEffect } from 'react'
import { Grid, Paper, Typography, Box } from '@mui/material'
import { getSocket } from '../services/socket'
import api from '../services/api'
import RealTimeWebhookFeed from '../components/Dashboard/RealTimeWebhookFeed'
import StatisticsCards from '../components/Dashboard/StatisticsCards'

const Dashboard = () => {
  const [recentWebhooks, setRecentWebhooks] = useState([])
  const [stats, setStats] = useState({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Fetch initial webhook logs
    fetchRecentLogs()
    fetchStats()

    // Listen for real-time webhook events
    const socket = getSocket()
    if (socket) {
      socket.on('webhook_received', (data) => {
        console.log('Webhook received:', data)
        setRecentWebhooks(prev => [data, ...prev].slice(0, 20))
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
            <Typography variant="h6" gutterBottom>
              Real-Time Webhook Feed
            </Typography>
            <RealTimeWebhookFeed
              webhooks={recentWebhooks}
              loading={loading}
              onWebhookDeleted={handleWebhookDeleted}
            />
          </Paper>
        </Grid>
      </Grid>
    </Box>
  )
}

export default Dashboard
