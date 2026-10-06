// A second, smaller Context: app-wide toast notifications.
// Any component calls notify('Saved!') or notify(error.message, 'error').
import { Alert, Snackbar } from '@mui/material'
import { createContext, useCallback, useContext, useState } from 'react'

const NotifyContext = createContext(() => {})

export function NotifyProvider({ children }) {
  const [toast, setToast] = useState(null)
  const notify = useCallback((message, severity = 'success') => {
    setToast({ message, severity, key: Date.now() })
  }, [])

  return (
    <NotifyContext.Provider value={notify}>
      {children}
      <Snackbar
        key={toast?.key}
        open={Boolean(toast)}
        autoHideDuration={4000}
        onClose={() => setToast(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        {toast ? (
          <Alert severity={toast.severity} variant="filled" onClose={() => setToast(null)}>
            {toast.message}
          </Alert>
        ) : undefined}
      </Snackbar>
    </NotifyContext.Provider>
  )
}

export const useNotify = () => useContext(NotifyContext)
