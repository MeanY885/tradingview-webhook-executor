import React from 'react'
import { Grid, Paper, Typography, Box } from '@mui/material'
import { CheckCircle, Error, Pending, ShowChart } from '@mui/icons-material'

const StatCard = ({ title, value, icon, color }) => (
  <Paper sx={{ p: 3 }}>
    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <Box>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          {title}
        </Typography>
        <Typography variant="h4">
          {value || 0}
        </Typography>
      </Box>
      <Box
        sx={{
          width: 56,
          height: 56,
          borderRadius: 2,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          bgcolor: `${color}.main`,
          color: 'white'
        }}
      >
        {icon}
      </Box>
    </Box>
  </Paper>
)

const StatisticsCards = ({ stats }) => {
  const total = Object.values(stats).reduce((sum, val) => sum + val, 0)

  return (
    <Grid container spacing={3}>
      <Grid item xs={12} sm={6} md={3}>
        <StatCard
          title="Total Webhooks"
          value={total}
          icon={<ShowChart />}
          color="primary"
        />
      </Grid>
      <Grid item xs={12} sm={6} md={3}>
        <StatCard
          title="Successful"
          value={stats.success || 0}
          icon={<CheckCircle />}
          color="success"
        />
      </Grid>
      <Grid item xs={12} sm={6} md={3}>
        <StatCard
          title="Failed"
          value={stats.failed || 0}
          icon={<Error />}
          color="error"
        />
      </Grid>
      <Grid item xs={12} sm={6} md={3}>
        <StatCard
          title="Invalid"
          value={stats.invalid || 0}
          icon={<Error />}
          color="warning"
        />
      </Grid>
    </Grid>
  )
}

export default StatisticsCards
