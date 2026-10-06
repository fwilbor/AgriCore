import AgricultureIcon from '@mui/icons-material/Agriculture'
import BuildIcon from '@mui/icons-material/Build'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import LocalGasStationIcon from '@mui/icons-material/LocalGasStation'
import PlaceIcon from '@mui/icons-material/Place'
import WarningIcon from '@mui/icons-material/Warning'
import {
  Alert,
  Box,
  Card,
  CardContent,
  CardHeader,
  Chip,
  Grid,
  LinearProgress,
  MenuItem,
  Skeleton,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material'
import { useState } from 'react'
import { BrandBadge } from '../components/Brand'
import FuelBar from '../components/FuelBar'
import MetricCard from '../components/MetricCard'
import PageHeader from '../components/PageHeader'
import StatusChip from '../components/StatusChip'
import { useAuth } from '../context/AuthContext'
import { useApi } from '../hooks'

const pct = (v) => `${(v * 100).toFixed(1)}%`

export default function DashboardPage() {
  const { hasRole } = useAuth()
  return hasRole('farm_hand') ? <FarmHandDashboard /> : <AnalyticsDashboard />
}

// ------------------------------------------------------------- Admin / Auditor
function AnalyticsDashboard() {
  const { data: s } = useApi('/analytics/summary')

  return (
    <>
      <PageHeader icon={<BrandBadge size={52} />} title="Operations Dashboard" subtitle="Equipment. Service. Insight. · live metrics across all Prairie Crest member farms" />
      <Grid container spacing={2} sx={{ mb: 3 }}>
        {[
          { label: 'Total Equipment', value: s?.total_equipment, caption: `${s?.equipment_by_status['In-Use'] ?? '–'} in use across ${s?.total_farms ?? '–'} farms`, icon: <AgricultureIcon />, tone: 'primary' },
          { label: 'In Maintenance', value: s?.equipment_by_status.Maintenance, caption: `${s?.maintenance_flagged_farms ?? '–'} farms over 30%`, icon: <BuildIcon />, tone: 'warning' },
          { label: 'Low Fuel (<20%)', value: s?.low_fuel_count, caption: 'Active units needing fuel', icon: <LocalGasStationIcon />, tone: 'error' },
          { label: 'Co-location Issues', value: s?.colocation_discrepancies, caption: 'Units assigned off-site', icon: <PlaceIcon />, tone: 'secondary' },
          { label: 'Active Jobs', value: s ? s.jobs_by_status.Pending + s.jobs_by_status['In-Progress'] : undefined, caption: `${s?.jobs_by_status['In-Progress'] ?? '–'} in progress`, icon: <WarningIcon />, tone: 'info' },
          { label: 'Job Completion Rate', value: s ? pct(s.overall_completion_rate) : undefined, caption: 'Completed ÷ finished jobs', icon: <CheckCircleIcon />, tone: 'success' },
        ].map((m) => (
          <Grid key={m.label} size={{ xs: 6, md: 4, lg: 2 }}>
            {s ? <MetricCard {...m} /> : <Skeleton variant="rounded" height={118} />}
          </Grid>
        ))}
      </Grid>

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, lg: 6 }}><LowFuelPanel /></Grid>
        <Grid size={{ xs: 12, lg: 6 }}><MaintenancePanel /></Grid>
        <Grid size={{ xs: 12, lg: 6 }}><ReliabilityPanel /></Grid>
        <Grid size={{ xs: 12, lg: 6 }}><SupervisorPanel /></Grid>
        <Grid size={12}><CoLocationPanel /></Grid>
      </Grid>
    </>
  )
}

function Panel({ question, title, action, children }) {
  return (
    <Card sx={{ height: '100%' }}>
      <CardHeader
        title={title}
        subheader={question}
        action={action}
        slotProps={{ title: { variant: 'h6' }, subheader: { variant: 'body2' } }}
        sx={{ flexWrap: 'wrap', gap: 1, '& .MuiCardHeader-action': { alignSelf: 'center', m: 0 } }}
      />
      <CardContent sx={{ pt: 0, overflowX: 'auto' }}>{children}</CardContent>
    </Card>
  )
}

function LowFuelPanel() {
  const [threshold, setThreshold] = useState(20)
  const { data } = useApi('/analytics/low-fuel', { threshold })
  return (
    <Panel
      title={`Low Fuel Alert ${data ? `· ${data.count}` : ''}`}
      question={`Which active units are below ${threshold}% fuel?`}
      action={
        <ToggleButtonGroup size="small" exclusive value={threshold} onChange={(_, v) => v && setThreshold(v)}>
          {[10, 20, 30].map((t) => <ToggleButton key={t} value={t}>{t}%</ToggleButton>)}
        </ToggleButtonGroup>
      }
    >
      <Table size="small">
        <TableHead>
          <TableRow><TableCell>Unit</TableCell><TableCell>Farm</TableCell><TableCell>Status</TableCell><TableCell sx={{ minWidth: 140 }}>Fuel</TableCell></TableRow>
        </TableHead>
        <TableBody>
          {data?.items.map((r) => (
            <TableRow key={r.id}>
              <TableCell>
                <Typography variant="body2" sx={{ fontFamily: 'monospace', whiteSpace: 'nowrap' }}>{r.serial_number}</Typography>
                <Typography variant="caption" color="text.secondary">{r.model}</Typography>
              </TableCell>
              <TableCell>{r.farm_name}</TableCell>
              <TableCell><StatusChip value={r.status} /></TableCell>
              <TableCell><FuelBar value={r.fuel_level} /></TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {data?.count === 0 && <Alert severity="success" sx={{ mt: 1 }}>All active units are above {threshold}%.</Alert>}
    </Panel>
  )
}

function MaintenancePanel() {
  const { data } = useApi('/analytics/maintenance-flags')
  return (
    <Panel
      title={`Maintenance Flags ${data ? `· ${data.flagged_count} flagged` : ''}`}
      question="Which farms have more than 30% of their equipment in maintenance?"
    >
      <Stack spacing={1.5}>
        {data?.items.map((f) => (
          <Box key={f.farm_id}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
              <Typography variant="body2" fontWeight={600} component="div">
                {f.farm_name} {f.flagged && <Chip size="small" color="error" label="FLAGGED" sx={{ ml: 1, height: 20 }} />}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {f.in_maintenance}/{f.total_equipment} · {pct(f.maintenance_pct)}
              </Typography>
            </Box>
            <LinearProgress
              variant="determinate"
              value={Math.min(100, f.maintenance_pct * 100)}
              color={f.flagged ? 'error' : f.maintenance_pct > 0.2 ? 'warning' : 'success'}
              sx={{ height: 8, borderRadius: 4 }}
            />
          </Box>
        ))}
      </Stack>
    </Panel>
  )
}

function ReliabilityPanel() {
  const { data } = useApi('/analytics/reliability')
  return (
    <Panel title="Reliability by Model" question="Field job completion vs failure ratio per equipment model">
      <Table size="small">
        <TableHead>
          <TableRow><TableCell>Model</TableCell><TableCell align="right">Done</TableCell><TableCell align="right">Failed</TableCell><TableCell width={170}>Completion</TableCell></TableRow>
        </TableHead>
        <TableBody>
          {data?.map((r) => (
            <TableRow key={r.model}>
              <TableCell>{r.model}</TableCell>
              <TableCell align="right">{r.completed}</TableCell>
              <TableCell align="right" sx={{ color: r.failure_rate > 0.2 ? 'error.main' : undefined, fontWeight: r.failure_rate > 0.2 ? 700 : 400 }}>{r.failed}</TableCell>
              <TableCell>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <LinearProgress variant="determinate" value={r.completion_rate * 100} color={r.completion_rate < 0.8 ? 'warning' : 'success'} sx={{ flex: 1, height: 8, borderRadius: 4 }} />
                  <Typography variant="body2" sx={{ minWidth: 48, textAlign: 'right' }}>{pct(r.completion_rate)}</Typography>
                </Box>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Panel>
  )
}

function SupervisorPanel() {
  const { data } = useApi('/analytics/supervisor-activity')
  const [selected, setSelected] = useState('')
  const current = data?.find((d) => d.supervisor_id === selected) || data?.[0]
  return (
    <Panel
      title="Reporting Lines"
      question="How many farmhands reporting to a supervisor have active field jobs?"
      action={
        data && (
          <TextField select size="small" label="Supervisor" value={current?.supervisor_id ?? ''} onChange={(e) => setSelected(e.target.value)} sx={{ minWidth: 200 }}>
            {data.map((d) => <MenuItem key={d.supervisor_id} value={d.supervisor_id}>{d.supervisor_name}</MenuItem>)}
          </TextField>
        )
      }
    >
      {current && (
        <Grid container spacing={2} sx={{ mb: 2 }}>
          <Grid size={4}><MetricCard label="Direct reports" value={current.direct_reports} /></Grid>
          <Grid size={4}><MetricCard label="With active jobs" value={current.reports_with_active_jobs} tone="success" /></Grid>
          <Grid size={4}><MetricCard label="Active jobs" value={current.active_jobs} tone="info" /></Grid>
        </Grid>
      )}
      <Table size="small">
        <TableHead>
          <TableRow><TableCell>Supervisor</TableCell><TableCell align="right">Farmhands</TableCell><TableCell align="right">With active jobs</TableCell><TableCell align="right">Active jobs</TableCell></TableRow>
        </TableHead>
        <TableBody>
          {data?.map((d) => (
            <TableRow key={d.supervisor_id} selected={d.supervisor_id === current?.supervisor_id}>
              <TableCell>{d.supervisor_name}</TableCell>
              <TableCell align="right">{d.direct_reports}</TableCell>
              <TableCell align="right">{d.reports_with_active_jobs}</TableCell>
              <TableCell align="right">{d.active_jobs}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Panel>
  )
}

function CoLocationPanel() {
  const { data } = useApi('/analytics/co-location')
  return (
    <Panel
      title={`Co-location Discrepancies ${data ? `· ${data.count}` : ''}`}
      question="Equipment assigned to farmhands who are NOT based at the same farm"
    >
      <Table size="small">
        <TableHead>
          <TableRow><TableCell>Serial</TableCell><TableCell>Model</TableCell><TableCell>Equipment farm</TableCell><TableCell>Assigned farmhand</TableCell><TableCell>Farmhand's farm</TableCell></TableRow>
        </TableHead>
        <TableBody>
          {data?.items.map((r) => (
            <TableRow key={r.equipment_id}>
              <TableCell sx={{ fontFamily: 'monospace' }}>{r.serial_number}</TableCell>
              <TableCell>{r.model}</TableCell>
              <TableCell>{r.equipment_farm}</TableCell>
              <TableCell>{r.farmhand}</TableCell>
              <TableCell sx={{ color: 'warning.main', fontWeight: 600 }}>{r.farmhand_farm ?? '— none —'}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Panel>
  )
}

// ------------------------------------------------------------------ Farm Hand
function FarmHandDashboard() {
  const { user } = useAuth()
  const { data: equipment } = useApi('/equipment')
  const { data: jobs } = useApi('/jobs')
  const active = jobs?.filter((j) => j.status === 'Pending' || j.status === 'In-Progress') ?? []
  const lowFuel = equipment?.filter((e) => e.fuel_level < 20 && ['Idle', 'In-Use'].includes(e.status)) ?? []

  return (
    <>
      <PageHeader icon={<BrandBadge size={52} />} title={`Welcome, ${user.full_name.split(' ')[0]}`} subtitle={`${user.farm_name ?? 'No home farm'} · Farm Hand`} />
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, sm: 4 }}><MetricCard label="My Equipment" value={equipment?.length ?? '–'} icon={<AgricultureIcon />} /></Grid>
        <Grid size={{ xs: 12, sm: 4 }}><MetricCard label="My Active Jobs" value={jobs ? active.length : '–'} icon={<WarningIcon />} tone="info" /></Grid>
        <Grid size={{ xs: 12, sm: 4 }}><MetricCard label="Units Low on Fuel" value={equipment ? lowFuel.length : '–'} icon={<LocalGasStationIcon />} tone="error" /></Grid>
      </Grid>
      <Card>
        <CardHeader title="My active field jobs" subheader="Update status and attach service reports on the Field Jobs page" />
        <CardContent sx={{ pt: 0, overflowX: 'auto' }}>
          <Table size="small">
            <TableHead>
              <TableRow><TableCell>Job</TableCell><TableCell>Equipment</TableCell><TableCell>Priority</TableCell><TableCell>Status</TableCell><TableCell>Scheduled</TableCell></TableRow>
            </TableHead>
            <TableBody>
              {active.map((j) => (
                <TableRow key={j.id}>
                  <TableCell>{j.title}</TableCell>
                  <TableCell sx={{ fontFamily: 'monospace' }}>{j.equipment_serial}</TableCell>
                  <TableCell><StatusChip value={j.priority} /></TableCell>
                  <TableCell><StatusChip value={j.status} /></TableCell>
                  <TableCell>{j.scheduled_date}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {jobs && active.length === 0 && <Alert severity="info" sx={{ mt: 1 }}>No active jobs right now.</Alert>}
        </CardContent>
      </Card>
    </>
  )
}
