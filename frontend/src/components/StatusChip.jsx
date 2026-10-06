import { Chip } from '@mui/material'

const COLORS = {
  // equipment
  Idle: 'default',
  'In-Use': 'info',
  Maintenance: 'warning',
  Retired: 'default',
  // jobs
  Pending: 'default',
  'In-Progress': 'info',
  Completed: 'success',
  Failed: 'error',
  // priority
  Low: 'default',
  Medium: 'primary',
  Critical: 'error',
  // roles
  admin: 'primary',
  farm_hand: 'secondary',
  auditor: 'info',
}

export default function StatusChip({ value, label, variant }) {
  if (!value) return null
  return (
    <Chip
      size="small"
      label={label || value}
      color={COLORS[value] || 'default'}
      variant={variant || (value === 'Retired' || value === 'Low' ? 'outlined' : 'filled')}
      sx={{ fontWeight: 600 }}
    />
  )
}
