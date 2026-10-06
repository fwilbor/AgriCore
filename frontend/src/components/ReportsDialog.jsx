// Lists a job's service reports and (for Admin / Farm Hand) uploads new ones.
// Upload: browser -> FastAPI (multipart) -> boto3 -> S3; the s3:// URL is saved in PostgreSQL.
// View:   FastAPI returns a short-lived presigned URL, which we open in a new tab.
import CloudUploadIcon from '@mui/icons-material/CloudUpload'
import DescriptionIcon from '@mui/icons-material/Description'
import OpenInNewIcon from '@mui/icons-material/OpenInNew'
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material'
import { useState } from 'react'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useNotify } from '../context/NotifyContext'
import { useApi } from '../hooks'

const ACCEPT = '.png,.jpg,.jpeg,.webp,.txt,.pdf'
const formatSize = (bytes) => (bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(1)} KB`)

export default function ReportsDialog({ job, onClose, onUploaded }) {
  const { hasRole } = useAuth()
  const notify = useNotify()
  const canUpload = hasRole('admin', 'farm_hand')
  const { data: reports, reload } = useApi(job ? `/jobs/${job.id}/reports` : null)
  const [file, setFile] = useState(null)
  const [notes, setNotes] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  async function upload() {
    setBusy(true)
    setError(null)
    const form = new FormData()
    form.append('file', file)
    if (notes) form.append('notes', notes)
    try {
      await api.upload(`/jobs/${job.id}/reports`, form)
      notify(`Uploaded ${file.name} to S3`)
      setFile(null)
      setNotes('')
      reload()
      onUploaded?.()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function open(report) {
    try {
      const { url } = await api.get(`/reports/${report.id}/download-url`)
      window.open(url, '_blank', 'noopener')
    } catch (err) {
      notify(err.message, 'error')
    }
  }

  return (
    <Dialog open={Boolean(job)} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>
        Service reports
        <Typography variant="body2" color="text.secondary" component="span" sx={{ display: 'block' }}>
          Job #{job?.id} · {job?.title} · {job?.equipment_serial}
        </Typography>
      </DialogTitle>
      <DialogContent dividers>
        {reports?.length === 0 && <Alert severity="info">No reports attached yet.</Alert>}
        <List dense>
          {reports?.map((r) => (
            <ListItem
              key={r.id}
              secondaryAction={
                <Tooltip title="Open via presigned S3 URL">
                  <IconButton edge="end" onClick={() => open(r)}><OpenInNewIcon /></IconButton>
                </Tooltip>
              }
            >
              <ListItemIcon><DescriptionIcon /></ListItemIcon>
              <ListItemText
                primary={r.file_name}
                secondary={
                  <>
                    {r.notes && <span>{r.notes}<br /></span>}
                    <span>{r.uploaded_by_name ?? 'Unknown'} · {new Date(r.created_at).toLocaleString()} · {formatSize(r.file_size)}</span>
                    <br />
                    <span style={{ fontFamily: 'monospace', fontSize: 11, wordBreak: 'break-all' }}>{r.file_url}</span>
                  </>
                }
              />
            </ListItem>
          ))}
        </List>

        {canUpload && (
          <>
            <Divider sx={{ my: 2 }} />
            <Typography variant="subtitle2" gutterBottom>Attach a new report</Typography>
            <Stack spacing={2}>
              {error && <Alert severity="error">{error}</Alert>}
              <Box>
                <Button component="label" variant="outlined" startIcon={<CloudUploadIcon />}>
                  {file ? file.name : 'Choose image, .txt or .pdf'}
                  <input hidden type="file" accept={ACCEPT} onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
                </Button>
              </Box>
              <TextField label="Notes" multiline minRows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
            </Stack>
          </>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={onClose}>Close</Button>
        {canUpload && (
          <Button variant="contained" disabled={!file || busy} onClick={upload} startIcon={<CloudUploadIcon />}>
            {busy ? 'Uploading…' : 'Upload to S3'}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  )
}
