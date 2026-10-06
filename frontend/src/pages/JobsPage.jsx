import AddIcon from '@mui/icons-material/Add'
import AttachFileIcon from '@mui/icons-material/AttachFile'
import CancelIcon from '@mui/icons-material/Cancel'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import DeleteIcon from '@mui/icons-material/Delete'
import EditIcon from '@mui/icons-material/Edit'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import { Badge, Button, Chip, Stack } from '@mui/material'
import { GridActionsCellItem } from '@mui/x-data-grid'
import { useMemo, useState } from 'react'
import { api } from '../api/client'
import AppDataGrid from '../components/AppDataGrid'
import FormDialog from '../components/FormDialog'
import PageHeader from '../components/PageHeader'
import ReportsDialog from '../components/ReportsDialog'
import StatusChip from '../components/StatusChip'
import { useAuth } from '../context/AuthContext'
import { useNotify } from '../context/NotifyContext'
import { useApi } from '../hooks'

const STATUSES = ['Pending', 'In-Progress', 'Completed', 'Failed']
const PRIORITIES = ['Low', 'Medium', 'Critical']
const PRIORITY_ORDER = { Low: 0, Medium: 1, Critical: 2 }

export default function JobsPage() {
  const { hasRole } = useAuth()
  const isAdmin = hasRole('admin')
  const canChangeStatus = hasRole('admin', 'farm_hand')
  const notify = useNotify()
  const { data, loading, reload } = useApi('/jobs')
  const { data: equipment } = useApi(isAdmin ? '/equipment' : null)
  const { data: hands } = useApi(isAdmin ? '/users' : null, { role: 'farm_hand' })
  const [statusFilter, setStatusFilter] = useState('All')
  const [dialog, setDialog] = useState(null)
  const [reportsJob, setReportsJob] = useState(null)

  const rows = useMemo(
    () => (data || []).filter((r) => statusFilter === 'All' || r.status === statusFilter),
    [data, statusFilter],
  )

  async function changeStatus(row, status) {
    try {
      await api.patch(`/jobs/${row.id}/status`, { status })
      notify(`Job #${row.id} → ${status}`)
      reload()
    } catch (err) {
      notify(err.message, 'error')
    }
  }

  async function save(payload) {
    if (dialog.mode === 'create') {
      await api.post('/jobs', payload)
      notify('Field job created')
    } else {
      await api.patch(`/jobs/${dialog.row.id}`, payload)
      notify('Field job updated')
    }
    reload()
  }

  async function remove(row) {
    if (!window.confirm(`Delete job #${row.id} "${row.title}"?`)) return
    try {
      await api.del(`/jobs/${row.id}`)
      notify('Field job deleted')
      reload()
    } catch (err) {
      notify(err.message, 'error')
    }
  }

  const fields = [
    { name: 'title', label: 'Title', required: true },
    { name: 'priority', label: 'Priority', type: 'select', options: PRIORITIES.map((p) => ({ value: p, label: p })) },
    { name: 'status', label: 'Status', type: 'select', options: STATUSES.map((s) => ({ value: s, label: s })) },
    {
      name: 'equipment_id', label: 'Equipment', type: 'select', required: true,
      options: (equipment || []).filter((e) => e.status !== 'Retired').map((e) => ({ value: e.id, label: `${e.serial_number} · ${e.model} · ${e.farm_name}` })),
    },
    { name: 'operator_id', label: 'Operator (farm hand)', type: 'select', nullable: true, options: (hands || []).map((h) => ({ value: h.id, label: `${h.full_name} (${h.farm_name ?? 'no farm'})` })) },
    { name: 'scheduled_date', label: 'Scheduled date', type: 'date', nullable: true },
  ]

  const columns = [
    { field: 'id', headerName: '#', width: 70 },
    { field: 'title', headerName: 'Title', flex: 1.4, minWidth: 220 },
    {
      field: 'priority', headerName: 'Priority', width: 110,
      renderCell: (p) => <StatusChip value={p.value} />,
      sortComparator: (a, b) => PRIORITY_ORDER[a] - PRIORITY_ORDER[b],
    },
    { field: 'status', headerName: 'Status', width: 130, renderCell: (p) => <StatusChip value={p.value} /> },
    { field: 'equipment_serial', headerName: 'Equipment', width: 150, renderCell: (p) => <span style={{ fontFamily: 'monospace' }}>{p.value}</span> },
    { field: 'equipment_model', headerName: 'Model', flex: 1, minWidth: 160 },
    { field: 'farm_name', headerName: 'Farm', flex: 1, minWidth: 150 },
    { field: 'operator_name', headerName: 'Operator', width: 140, valueGetter: (v) => v ?? '—' },
    { field: 'scheduled_date', headerName: 'Scheduled', width: 110 },
    {
      field: 'actions',
      type: 'actions',
      headerName: 'Actions',
      width: isAdmin ? 130 : 100,
      getActions: ({ row }) => {
        const finished = row.status === 'Completed' || row.status === 'Failed'
        const items = [
          <GridActionsCellItem
            key="reports"
            icon={<Badge badgeContent={row.report_count} color="primary" max={9}><AttachFileIcon /></Badge>}
            label="Service reports"
            onClick={() => setReportsJob(row)}
          />,
        ]
        if (canChangeStatus && (isAdmin || !finished)) {
          if (row.status === 'Pending')
            items.push(<GridActionsCellItem key="start" showInMenu icon={<PlayArrowIcon />} label="Start (In-Progress)" onClick={() => changeStatus(row, 'In-Progress')} />)
          if (!finished) {
            items.push(<GridActionsCellItem key="done" showInMenu icon={<CheckCircleIcon color="success" />} label="Mark Completed" onClick={() => changeStatus(row, 'Completed')} />)
            items.push(<GridActionsCellItem key="fail" showInMenu icon={<CancelIcon color="error" />} label="Mark Failed" onClick={() => changeStatus(row, 'Failed')} />)
          }
        }
        if (isAdmin) {
          items.push(<GridActionsCellItem key="edit" showInMenu icon={<EditIcon />} label="Edit" onClick={() => setDialog({ mode: 'edit', row })} />)
          items.push(<GridActionsCellItem key="del" showInMenu icon={<DeleteIcon />} label="Delete" onClick={() => remove(row)} />)
        }
        return items
      },
    },
  ]

  return (
    <>
      <PageHeader
        title="Field Jobs"
        subtitle={hasRole('farm_hand') ? 'Jobs assigned to you' : 'Planting, spraying, harvest and irrigation work orders'}
        action={isAdmin && <Button variant="contained" startIcon={<AddIcon />} onClick={() => setDialog({ mode: 'create' })}>New field job</Button>}
      />
      <Stack direction="row" spacing={1} sx={{ mb: 2, flexWrap: 'wrap', rowGap: 1 }}>
        {['All', ...STATUSES].map((s) => (
          <Chip
            key={s}
            label={`${s} (${s === 'All' ? data?.length ?? 0 : (data || []).filter((r) => r.status === s).length})`}
            color={statusFilter === s ? 'primary' : 'default'}
            variant={statusFilter === s ? 'filled' : 'outlined'}
            onClick={() => setStatusFilter(s)}
          />
        ))}
      </Stack>
      <AppDataGrid rows={rows} columns={columns} loading={loading} searchPlaceholder="Search title, equipment, farm, operator…" />
      <FormDialog
        open={Boolean(dialog)}
        title={dialog?.mode === 'edit' ? `Edit job #${dialog.row.id}` : 'New field job'}
        fields={fields}
        initialValues={dialog?.mode === 'edit' ? dialog.row : { priority: 'Medium', status: 'Pending' }}
        onClose={() => setDialog(null)}
        onSubmit={save}
      />
      <ReportsDialog job={reportsJob} onClose={() => setReportsJob(null)} onUploaded={reload} />
    </>
  )
}
