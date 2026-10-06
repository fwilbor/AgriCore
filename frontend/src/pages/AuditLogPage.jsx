import { Chip } from '@mui/material'
import AppDataGrid from '../components/AppDataGrid'
import PageHeader from '../components/PageHeader'
import { useApi } from '../hooks'

const ACTION_COLORS = {
  CREATE: 'success', UPDATE: 'info', DELETE: 'error', DEACTIVATE: 'error',
  STATUS_CHANGE: 'warning', UPLOAD: 'secondary', LOGIN: 'default', SEED: 'default',
}

export default function AuditLogPage() {
  const { data, loading } = useApi('/audit-logs')

  const columns = [
    { field: 'created_at', headerName: 'When', width: 190, type: 'dateTime', valueGetter: (v) => v && new Date(v) },
    { field: 'user_email', headerName: 'User', flex: 1, minWidth: 220, valueGetter: (v) => v ?? 'system' },
    { field: 'action', headerName: 'Action', width: 150, renderCell: (p) => <Chip size="small" label={p.value} color={ACTION_COLORS[p.value] || 'default'} /> },
    { field: 'entity_type', headerName: 'Entity', width: 140 },
    { field: 'entity_id', headerName: 'ID', width: 80 },
    { field: 'detail', headerName: 'Detail', flex: 2, minWidth: 280 },
  ]

  return (
    <>
      <PageHeader title="Audit Log" subtitle="Every login, change, status update and upload - use the search box to filter" />
      <AppDataGrid
        rows={data || []}
        columns={columns}
        loading={loading}
        pageSize={25}
        searchPlaceholder="Search user, action, detail…"
        initialState={{ sorting: { sortModel: [{ field: 'created_at', sort: 'desc' }] } }}
      />
    </>
  )
}
