import React, { useState } from 'react'
import {
  Paper,
  Typography,
  TextField,
  Button,
  Alert,
  Box,
  CircularProgress,
  Grid
} from '@mui/material'
import api from '../../services/api'

const PasswordChange = ({ userId }) => {
  const [formData, setFormData] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: ''
  })
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState(null)
  const [errors, setErrors] = useState({})

  const validateForm = () => {
    const newErrors = {}

    // Validate current password (required for self-change)
    if (!userId && !formData.currentPassword) {
      newErrors.currentPassword = 'Current password is required'
    }

    // Validate new password minimum length (8 characters)
    if (!formData.newPassword) {
      newErrors.newPassword = 'New password is required'
    } else if (formData.newPassword.length < 8) {
      newErrors.newPassword = 'Password must be at least 8 characters'
    }

    // Validate passwords match
    if (formData.newPassword !== formData.confirmPassword) {
      newErrors.confirmPassword = 'Passwords do not match'
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleChange = (field) => (event) => {
    setFormData({ ...formData, [field]: event.target.value })
    // Clear field error when user starts typing
    if (errors[field]) {
      setErrors({ ...errors, [field]: null })
    }
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setMessage(null)

    if (!validateForm()) {
      return
    }

    setSaving(true)

    try {
      const payload = {
        new_password: formData.newPassword
      }

      // Include current password for self-change
      if (!userId) {
        payload.current_password = formData.currentPassword
      } else {
        // Admin changing another user's password
        payload.user_id = userId
      }

      await api.post('/api/auth/change-password', payload)

      setMessage({ type: 'success', text: 'Password changed successfully' })
      // Clear form on success
      setFormData({
        currentPassword: '',
        newPassword: '',
        confirmPassword: ''
      })
    } catch (error) {
      const errorMessage = error.response?.data?.error || 'Failed to change password'
      setMessage({ type: 'error', text: errorMessage })
    } finally {
      setSaving(false)
    }
  }

  const isFormValid = () => {
    const hasCurrentPassword = userId || formData.currentPassword
    const hasNewPassword = formData.newPassword.length >= 8
    const passwordsMatch = formData.newPassword === formData.confirmPassword
    return hasCurrentPassword && hasNewPassword && passwordsMatch
  }

  return (
    <Paper sx={{ p: 3, mb: 3 }}>
      <Typography variant="h6" gutterBottom>
        Change Password
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        {userId
          ? 'Set a new password for this user.'
          : 'Update your account password. You will need to enter your current password for verification.'}
      </Typography>

      {message && (
        <Alert severity={message.type} sx={{ mb: 2 }} onClose={() => setMessage(null)}>
          {message.text}
        </Alert>
      )}

      <form onSubmit={handleSubmit}>
        <Grid container spacing={2}>
          {/* Current password - only shown for self-change */}
          {!userId && (
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Current Password"
                type="password"
                value={formData.currentPassword}
                onChange={handleChange('currentPassword')}
                error={!!errors.currentPassword}
                helperText={errors.currentPassword}
                disabled={saving}
              />
            </Grid>
          )}

          <Grid item xs={12}>
            <TextField
              fullWidth
              label="New Password"
              type="password"
              value={formData.newPassword}
              onChange={handleChange('newPassword')}
              error={!!errors.newPassword}
              helperText={errors.newPassword || 'Minimum 8 characters'}
              disabled={saving}
            />
          </Grid>

          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Confirm New Password"
              type="password"
              value={formData.confirmPassword}
              onChange={handleChange('confirmPassword')}
              error={!!errors.confirmPassword}
              helperText={errors.confirmPassword}
              disabled={saving}
            />
          </Grid>

          <Grid item xs={12}>
            <Button
              type="submit"
              variant="contained"
              disabled={saving || !isFormValid()}
            >
              {saving ? <CircularProgress size={24} /> : 'Change Password'}
            </Button>
          </Grid>
        </Grid>
      </form>
    </Paper>
  )
}

export default PasswordChange
