import AddIcon from '@mui/icons-material/Add'
import DeleteIcon from '@mui/icons-material/Delete'
import EditIcon from '@mui/icons-material/Edit'
import { Box, Button, LinearProgress, Typography } from '@mui/material'
import { GridActionsCellItem } from '@mui/x-data-grid'
import { useState } from 'react'
import { api } from '../api/client'
import AppDataGrid from '../components/AppDataGrid'
import FormDialog from '../components/FormDialog'
import PageHeader from '../components/PageHeader'
import { useAuth } from '../context/AuthContext'
import { useNotify } from '../context/NotifyContext'
import { useApi } from '../hooks'

export default function FarmsPage() {
  const { hasRole } = useAuth()
  const isAdmin = hasRole('admin')
  const notify = useNotify()
  const { data, loading, reload } = useApi('/farms')
  const { data: admins } = useApi(isAdmin ? '/users' : null, { role: 'admin' })
  const [dialog, setDialog] = useState(null)

  const fields = [
    { name: 'name', label: 'Farm name', required: true },
    { name: 'location_region', label: 'Region', required: true },
    { name: 'capacity', label: 'Equipment capacity', type: 'number', required: true },
    { name: 'supervisor_id', label: 'Regional Agronomy Supervisor', type: 'select', nullable: true, options: (admins || []).map((u) => ({ value: u.id, label: u.full_name })) },
  ]

  async function save(payload) {
    if (dialog.mode === 'create') await api.post('/farms', payload)
    else await api.patch(`/farms/${dialog.row.id}`, payload)
    notify(dialog.mode === 'create' ? 'Farm created' : 'Farm updated')
    reload()
  }

  async function remove(row) {
    if (!window.confirm(`Delete ${row.name}?`)) return
    try {
      await api.del(`/farms/${row.id}`)
      notify('Farm deleted')
      reload()
    } catch (err) {
      notify(err.message, 'error')
    }
  }

  const columns = [
    { field: 'name', headerName: 'Farm', flex: 1, minWidth: 180 },
    { field: 'location_region', headerName: 'Region', width: 160 },
    { field: 'supervisor_name', headerName: 'Supervisor', flex: 1, minWidth: 160 },
    {
      field: 'utilization', headerName: 'Units / capacity', width: 200,
      valueGetter: (_, row) => row.equipment_count / row.capacity,
      renderCell: ({ row }) => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%', height: '100%' }}>
          <LinearProgress variant="determinate" value={Math.min(100, (row.equipment_count / row.capacity) * 100)} sx={{ flex: 1, height: 8, borderRadius: 4 }} />
          <Typography variant="body2">{row.equipment_count}/{row.capacity}</Typography>
        </Box>
      ),
    },
  ]
  if (isAdmin) {
    columns.push({
      field: 'actions', type: 'actions', width: 90,
      getActions: ({ row }) => [
        <GridActionsCellItem key="edit" icon={<EditIcon />} label="Edit" onClick={() => setDialog({ mode: 'edit', row })} />,
        <GridActionsCellItem key="del" icon={<DeleteIcon />} label="Delete" onClick={() => remove(row)} />,
      ],
    })
  }

  return (
    <>
      <PageHeader
        title="Farms"
        subtitle="Member farms and grain elevator sites"
        action={isAdmin && <Button variant="contained" startIcon={<AddIcon />} onClick={() => setDialog({ mode: 'create' })}>Add farm</Button>}
      />
      <AppDataGrid rows={data || []} columns={columns} loading={loading} searchPlaceholder="Search farms…" sx={{ minHeight: 0 }} />
      <FormDialog
        open={Boolean(dialog)}
        title={dialog?.mode === 'edit' ? `Edit ${dialog.row.name}` : 'Add farm'}
        fields={fields}
        initialValues={dialog?.mode === 'edit' ? dialog.row : {}}
        onClose={() => setDialog(null)}
        onSubmit={save}
      />
    </>
  )
}
