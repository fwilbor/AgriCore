// Reusable create/edit dialog driven by a list of field definitions:
//   { name, label, type: 'text'|'number'|'select'|'date'|'password', options, required, nullable }
// It returns only the values; the page decides which API call to make.
// Server-side validation errors (Pydantic 422s) are shown inside the dialog.
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  Stack,
  TextField,
} from '@mui/material'
import { useEffect, useState } from 'react'

const EMPTY = '__none__'

export default function FormDialog({ open, title, fields, initialValues, onClose, onSubmit, submitLabel = 'Save' }) {
  const [values, setValues] = useState({})
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (open) {
      setValues(initialValues || {})
      setError(null)
    }
  }, [open, initialValues])

  const set = (name, value) => setValues((v) => ({ ...v, [name]: value }))

  async function handleSubmit(event) {
    event.preventDefault()
    setSaving(true)
    setError(null)
    // Convert form strings back into the types the API expects.
    const payload = {}
    for (const f of fields) {
      let v = values[f.name]
      if (v === undefined) continue
      if (v === '' || v === EMPTY) v = f.nullable ? null : undefined
      else if (f.type === 'number') v = Number(v)
      if (v !== undefined) payload[f.name] = v
    }
    try {
      await onSubmit(payload)
      onClose()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <form onSubmit={handleSubmit} noValidate>
        <DialogTitle>{title}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            {error && <Alert severity="error">{error}</Alert>}
            {fields.map((f) => (
              <TextField
                key={f.name}
                label={f.label}
                type={f.type === 'select' ? undefined : f.type || 'text'}
                select={f.type === 'select'}
                required={f.required}
                value={values[f.name] ?? (f.type === 'select' && f.nullable ? EMPTY : '')}
                onChange={(e) => set(f.name, e.target.value)}
                helperText={f.helperText}
                slotProps={{
                  inputLabel: f.type === 'date' ? { shrink: true } : undefined,
                  htmlInput: f.type === 'number' ? { step: 'any' } : undefined,
                }}
                fullWidth
              >
                {f.type === 'select' && f.nullable && <MenuItem value={EMPTY}>— None —</MenuItem>}
                {f.type === 'select' &&
                  (f.options || []).map((o) => (
                    <MenuItem key={o.value} value={o.value}>
                      {o.label}
                    </MenuItem>
                  ))}
              </TextField>
            ))}
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="contained" disabled={saving}>
            {saving ? 'Saving…' : submitLabel}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  )
}
