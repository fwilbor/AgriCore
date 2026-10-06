import AddIcon from '@mui/icons-material/Add'
import BlockIcon from '@mui/icons-material/Block'
import EditIcon from '@mui/icons-material/Edit'
import { Button, Chip } from '@mui/material'
import { GridActionsCellItem } from '@mui/x-data-grid'
import { useState } from 'react'
import { api } from '../api/client'
import AppDataGrid from '../components/AppDataGrid'
import FormDialog from '../components/FormDialog'
import PageHeader from '../components/PageHeader'
import StatusChip from '../components/StatusChip'
import { ROLE_LABELS, useAuth } from '../context/AuthContext'
import { useNotify } from '../context/NotifyContext'
import { useApi } from '../hooks'

export default function UsersPage() {
  const { hasRole, user: me } = useAuth()
  const isAdmin = hasRole('admin')
  const notify = useNotify()
  const { data, loading, reload } = useApi('/users')
  const { data: farms } = useApi('/farms')
  const [dialog, setDialog] = useState(null)

  const roleOptions = Object.entries(ROLE_LABELS).map(([value, label]) => ({ value, label }))
  const supervisors = (data || []).filter((u) => u.job_title === 'Regional Agronomy Supervisor')
  const baseFields = [
    { name: 'full_name', label: 'Full name', required: true },
    { name: 'role', label: 'Role', type: 'select', required: true, options: roleOptions },
    { name: 'job_title', label: 'Job title', nullable: true },
    { name: 'farm_id', label: 'Home farm', type: 'select', nullable: true, options: (farms || []).map((f) => ({ value: f.id, label: f.name })) },
    { name: 'supervisor_id', label: 'Reports to', type: 'select', nullable: true, options: supervisors.map((s) => ({ value: s.id, label: s.full_name })) },
  ]
  const fields =
    dialog?.mode === 'create'
      ? [{ name: 'email', label: 'Email', required: true }, ...baseFields, { name: 'password', label: 'Password (min 8 chars)', type: 'password', required: true }]
      : [...baseFields, { name: 'password', label: 'New password (optional)', type: 'password' }]

  async function save(payload) {
    if (dialog.mode === 'create') await api.post('/users', payload)
    else await api.patch(`/users/${dialog.row.id}`, payload)
    notify(dialog.mode === 'create' ? 'User created' : 'User updated')
    reload()
  }

  async function deactivate(row) {
    if (!window.confirm(`Deactivate ${row.full_name}? They will no longer be able to sign in.`)) return
    try {
      await api.del(`/users/${row.id}`)
      notify('User deactivated')
      reload()
    } catch (err) {
      notify(err.message, 'error')
    }
  }

  const columns = [
    { field: 'full_name', headerName: 'Name', flex: 1, minWidth: 160 },
    { field: 'email', headerName: 'Email', flex: 1.2, minWidth: 220 },
    { field: 'role', headerName: 'Role', width: 190, renderCell: (p) => <StatusChip value={p.value} label={ROLE_LABELS[p.value]} /> },
    { field: 'job_title', headerName: 'Title', flex: 1, minWidth: 180 },
    { field: 'farm_name', headerName: 'Home farm', flex: 1, minWidth: 160, valueGetter: (v) => v ?? '—' },
    { field: 'supervisor_name', headerName: 'Reports to', width: 150, valueGetter: (v) => v ?? '—' },
    { field: 'is_active', headerName: 'Active', width: 90, renderCell: (p) => <Chip size="small" label={p.value ? 'Yes' : 'No'} color={p.value ? 'success' : 'default'} variant="outlined" /> },
  ]
  if (isAdmin) {
    columns.push({
      field: 'actions', type: 'actions', width: 90,
      getActions: ({ row }) => [
        <GridActionsCellItem key="edit" icon={<EditIcon />} label="Edit" onClick={() => setDialog({ mode: 'edit', row })} />,
        <GridActionsCellItem key="off" icon={<BlockIcon />} label="Deactivate" disabled={row.id === me.id || !row.is_active} onClick={() => deactivate(row)} />,
      ],
    })
  }

  return (
    <>
      <PageHeader
        title="Users"
        subtitle="Accounts, roles and reporting lines"
        action={isAdmin && <Button variant="contained" startIcon={<AddIcon />} onClick={() => setDialog({ mode: 'create' })}>Add user</Button>}
      />
      <AppDataGrid rows={data || []} columns={columns} loading={loading} searchPlaceholder="Search people, roles, farms…" />
      <FormDialog
        open={Boolean(dialog)}
        title={dialog?.mode === 'edit' ? `Edit ${dialog.row.full_name}` : 'Add user'}
        fields={fields}
        initialValues={dialog?.mode === 'edit' ? dialog.row : { role: 'farm_hand', job_title: 'Farm Hand' }}
        onClose={() => setDialog(null)}
        onSubmit={save}
      />
    </>
  )
}
