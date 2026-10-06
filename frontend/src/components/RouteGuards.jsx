import { Alert, Box } from '@mui/material'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

// Redirect to /login when nobody is signed in.
export function RequireAuth({ children }) {
  const { isAuthenticated } = useAuth()
  const location = useLocation()
  if (!isAuthenticated) return <Navigate to="/login" replace state={{ from: location }} />
  return children
}

// Hide a whole page from roles that may not see it. (The API enforces the
// same rule - UI checks are for convenience, the backend is the real gate.)
export function RequireRole({ roles, children }) {
  const { hasRole } = useAuth()
  if (!hasRole(...roles)) {
    return (
      <Box p={3}>
        <Alert severity="warning">Your role does not have access to this page.</Alert>
      </Box>
    )
  }
  return children
}
