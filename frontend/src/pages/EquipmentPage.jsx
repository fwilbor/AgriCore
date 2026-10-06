import AddIcon from '@mui/icons-material/Add'
import DeleteIcon from '@mui/icons-material/Delete'
import EditIcon from '@mui/icons-material/Edit'
import { Button, Chip, Stack } from '@mui/material'
import { GridActionsCellItem } from '@mui/x-data-grid'
import { useMemo, useState } from 'react'
import { api } from '../api/client'
import AppDataGrid from '../components/AppDataGrid'
import FormDialog from '../components/FormDialog'
import FuelBar from '../components/FuelBar'
import PageHeader from '../components/PageHeader'
import StatusChip from '../components/StatusChip'
import { useAuth } from '../context/AuthContext'
import { useNotify } from '../context/NotifyContext'
import { useApi } from '../hooks'

const STATUSES = ['Idle', 'In-Use', 'Maintenance', 'Retired']
const TYPES = ['Tractor', 'Combine', 'Sprayer', 'Irrigation Pump']

export default function EquipmentPage() {
  const { hasRole } = useAuth()
  const isAdmin = hasRole('admin')
  const notify = useNotify()
  const { data, loading, reload } = useApi('/equipment')
  const { data: farms } = useApi('/farms')
  const { data: hands } = useApi(isAdmin ? '/users' : null, { role: 'farm_hand' })
  const [statusFilter, setStatusFilter] = useState('All')
  const [dialog, setDialog] = useState(null) // null | {mode: 'create'} | {mode: 'edit', row}

  const rows = useMemo(
    () => (data || []).filter((r) => statusFilter === 'All' || r.status === statusFilter),
    [data, statusFilter],
  )
  const counts = useMemo(() => {
    const c = { All: data?.length ?? 0 }
    STATUSES.forEach((s) => (c[s] = (data || []).filter((r) => r.status === s).length))
    return c
  }, [data])

  const fields = [
    { name: 'serial_number', label: 'Serial number', required: true, helperText: 'Uppercase letters, digits, hyphens (e.g. JD8R-2024-0100)' },
    { name: 'model', label: 'Model', required: true },
    { name: 'equipment_type', label: 'Type', type: 'select', required: true, options: TYPES.map((t) => ({ value: t, label: t })) },
    { name: 'status', label: 'Status', type: 'select', options: STATUSES.map((s) => ({ value: s, label: s })) },
    { name: 'fuel_level', label: 'Fuel level (%)', type: 'number', required: true, helperText: '0 – 100 (validated by Pydantic on the server)' },
    { name: 'facility_id', label: 'Farm', type: 'select', required: true, options: (farms || []).map((f) => ({ value: f.id, label: f.name })) },
    { name: 'assigned_to_id', label: 'Assigned farm hand', type: 'select', nullable: true, options: (hands || []).map((h) => ({ value: h.id, label: `${h.full_name} (${h.farm_name ?? 'no farm'})` })) },
    { name: 'last_service_date', label: 'Last service date', type: 'date', nullable: true },
  ]

  async function save(payload) {
    if (dialog.mode === 'create') {
      await api.post('/equipment', payload)
      notify('Equipment created')
    } else {
      await api.patch(`/equipment/${dialog.row.id}`, payload)
      notify('Equipment updated')
    }
    reload()
  }

  async function remove(row) {
    if (!window.confirm(`Delete ${row.serial_number}?`)) return
    try {
      await api.del(`/equipment/${row.id}`)
      notify('Equipment deleted')
      reload()
    } catch (err) {
      notify(err.message, 'error')
    }
  }

  const columns = [
    { field: 'serial_number', headerName: 'Serial', width: 150, renderCell: (p) => <span style={{ fontFamily: 'monospace' }}>{p.value}</span> },
    { field: 'model', headerName: 'Model', flex: 1, minWidth: 170 },
    { field: 'equipment_type', headerName: 'Type', width: 130 },
    { field: 'status', headerName: 'Status', width: 130, renderCell: (p) => <StatusChip value={p.value} /> },
    { field: 'fuel_level', headerName: 'Fuel', type: 'number', width: 170, renderCell: (p) => <FuelBar value={p.value} /> },
    { field: 'farm_name', headerName: 'Farm', flex: 1, minWidth: 160 },
    { field: 'assigned_to_name', headerName: 'Assigned to', flex: 1, minWidth: 140, valueGetter: (v) => v ?? '—' },
    { field: 'last_service_date', headerName: 'Last service', width: 120 },
  ]
  if (isAdmin) {
    columns.push({
      field: 'actions',
      type: 'actions',
      width: 90,
      getActions: ({ row }) => [
        <GridActionsCellItem key="edit" icon={<EditIcon />} label="Edit" onClick={() => setDialog({ mode: 'edit', row })} />,
        <GridActionsCellItem key="del" icon={<DeleteIcon />} label="Delete" onClick={() => remove(row)} />,
      ],
    })
  }

  return (
    <>
      <PageHeader
        title="Equipment"
        subtitle={hasRole('farm_hand') ? 'Units assigned to you or used on your jobs' : 'Shared heavy-equipment pool across all farms'}
        action={isAdmin && <Button variant="contained" startIcon={<AddIcon />} onClick={() => setDialog({ mode: 'create' })}>Add equipment</Button>}
      />
      <Stack direction="row" spacing={1} sx={{ mb: 2, flexWrap: 'wrap', rowGap: 1 }}>
        {['All', ...STATUSES].map((s) => (
          <Chip
            key={s}
            label={`${s} (${counts[s] ?? 0})`}
            color={statusFilter === s ? 'primary' : 'default'}
            variant={statusFilter === s ? 'filled' : 'outlined'}
            onClick={() => setStatusFilter(s)}
          />
        ))}
      </Stack>
      <AppDataGrid
        rows={rows}
        columns={columns}
        loading={loading}
        searchPlaceholder="Search serial, model, farm, operator…"
        initialState={{ sorting: { sortModel: [{ field: 'serial_number', sort: 'asc' }] } }}
      />
      <FormDialog
        open={Boolean(dialog)}
        title={dialog?.mode === 'edit' ? `Edit ${dialog.row.serial_number}` : 'Add equipment'}
        fields={fields}
        initialValues={dialog?.mode === 'edit' ? dialog.row : { status: 'Idle', fuel_level: 100 }}
        onClose={() => setDialog(null)}
        onSubmit={save}
      />
    </>
  )
}
