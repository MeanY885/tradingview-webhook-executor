import React, { useState, useEffect } from 'react'
import {
  Box,
  Paper,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  Chip,
  TextField,
  MenuItem,
  Grid,
  CircularProgress
} from '@mui/material'
import { format } from 'date-fns'
import api from '../services/api'

const TradeHistory = () => {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(0)
  const [rowsPerPage, setRowsPerPage] = useState(25)
  const [total, setTotal] = useState(0)
  const [filters, setFilters] = useState({
    broker: '',
    status: '',
    symbol: ''
  })

  useEffect(() => {
    fetchLogs()
  }, [page, rowsPerPage, filters])

  const fetchLogs = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({
        page: page + 1,
        per_page: rowsPerPage,
        ...Object.fromEntries(Object.entries(filters).filter(([_, v]) => v))
      })

      const response = await api.get(`/api/webhook-logs?${params}`)
      setLogs(response.data.logs)
      setTotal(response.data.total)
    } catch (error) {
      console.error('Failed to fetch logs:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleChangePage = (event, newPage) => {
    setPage(newPage)
  }

  const handleChangeRowsPerPage = (event) => {
    setRowsPerPage(parseInt(event.target.value, 10))
    setPage(0)
  }

  const handleFilterChange = (field) => (event) => {
    setFilters({ ...filters, [field]: event.target.value })
    setPage(0)
  }

  const getStatusColor = (status) => {
    switch (status) {
      case 'success':
        return 'success'
      case 'failed':
        return 'error'
      case 'invalid':
        return 'warning'
      default:
        return 'default'
    }
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Trade History
      </Typography>

      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          Filters
        </Typography>
        <Grid container spacing={2}>
          <Grid item xs={12} sm={4}>
            <TextField
              fullWidth
              select
              label="Broker"
              value={filters.broker}
              onChange={handleFilterChange('broker')}
            >
              <MenuItem value="">All</MenuItem>
              <MenuItem value="blofin">Blofin</MenuItem>
              <MenuItem value="oanda">Oanda</MenuItem>
            </TextField>
          </Grid>
          <Grid item xs={12} sm={4}>
            <TextField
              fullWidth
              select
              label="Status"
              value={filters.status}
              onChange={handleFilterChange('status')}
            >
              <MenuItem value="">All</MenuItem>
              <MenuItem value="success">Success</MenuItem>
              <MenuItem value="failed">Failed</MenuItem>
              <MenuItem value="invalid">Invalid</MenuItem>
              <MenuItem value="pending">Pending</MenuItem>
            </TextField>
          </Grid>
          <Grid item xs={12} sm={4}>
            <TextField
              fullWidth
              label="Symbol"
              value={filters.symbol}
              onChange={handleFilterChange('symbol')}
              placeholder="e.g., BTCUSDT"
            />
          </Grid>
        </Grid>
      </Paper>

      <Paper>
        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Timestamp</TableCell>
                <TableCell>Broker</TableCell>
                <TableCell>Symbol</TableCell>
                <TableCell>Action</TableCell>
                <TableCell>Type</TableCell>
                <TableCell align="right">Quantity</TableCell>
                <TableCell align="right">Price</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Order ID</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={9} align="center">
                    <CircularProgress />
                  </TableCell>
                </TableRow>
              ) : logs.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={9} align="center">
                    <Typography color="text.secondary">
                      No trade history found
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : (
                logs.map((log) => (
                  <TableRow key={log.id} hover>
                    <TableCell>
                      {format(new Date(log.timestamp), 'MMM dd, yyyy HH:mm:ss')}
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={log.broker?.toUpperCase()}
                        size="small"
                        color={log.broker === 'blofin' ? 'primary' : 'secondary'}
                      />
                    </TableCell>
                    <TableCell>
                      {log.symbol}
                      {log.original_symbol && log.original_symbol !== log.symbol && (
                        <Typography variant="caption" color="text.secondary" display="block">
                          ({log.original_symbol})
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={log.action?.toUpperCase()}
                        size="small"
                        color={log.action === 'buy' ? 'success' : 'error'}
                        variant="outlined"
                      />
                    </TableCell>
                    <TableCell>{log.order_type}</TableCell>
                    <TableCell align="right">{log.quantity}</TableCell>
                    <TableCell align="right">
                      {log.price ? log.price.toFixed(2) : '-'}
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={log.status}
                        size="small"
                        color={getStatusColor(log.status)}
                      />
                      {log.error_message && (
                        <Typography variant="caption" color="error" display="block">
                          {log.error_message}
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                        {log.broker_order_id || '-'}
                      </Typography>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
        <TablePagination
          component="div"
          count={total}
          page={page}
          onPageChange={handleChangePage}
          rowsPerPage={rowsPerPage}
          onRowsPerPageChange={handleChangeRowsPerPage}
          rowsPerPageOptions={[10, 25, 50, 100]}
        />
      </Paper>
    </Box>
  )
}

export default TradeHistory
