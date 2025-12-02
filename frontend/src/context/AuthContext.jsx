import React, { createContext, useState, useEffect, useContext } from 'react'
import api from '../services/api'
import { connectSocket, disconnectSocket } from '../services/socket'

const AuthContext = createContext()

export const useAuth = () => useContext(AuthContext)

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Check if user is logged in
    const token = localStorage.getItem('access_token')
    if (token) {
      fetchCurrentUser()
    } else {
      setLoading(false)
    }
  }, [])

  const fetchCurrentUser = async () => {
    try {
      const response = await api.get('/api/auth/me')
      setUser(response.data)

      // Connect WebSocket
      const token = localStorage.getItem('access_token')
      connectSocket(token)
    } catch (error) {
      console.error('Failed to fetch user:', error)
      localStorage.removeItem('access_token')
    } finally {
      setLoading(false)
    }
  }

  const login = async (email, password) => {
    const response = await api.post('/api/auth/login', { email, password })
    const { access_token, user: userData } = response.data

    localStorage.setItem('access_token', access_token)
    setUser(userData)

    // Connect WebSocket
    connectSocket(access_token)

    return userData
  }

  const register = async (email, username, password) => {
    await api.post('/api/auth/register', { email, username, password })
    // Auto-login after registration
    return login(email, password)
  }

  const logout = () => {
    localStorage.removeItem('access_token')
    setUser(null)
    disconnectSocket()
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, fetchCurrentUser }}>
      {children}
    </AuthContext.Provider>
  )
}
