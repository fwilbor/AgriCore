import AgricultureIcon from '@mui/icons-material/Agriculture'
import BuildCircleIcon from '@mui/icons-material/BuildCircle'
import InsightsIcon from '@mui/icons-material/Insights'
import { Alert, Box, Button, Card, CardContent, Divider, Stack, TextField, Typography } from '@mui/material'
import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { LOGO_FULL } from '../components/Brand'
import { ROLE_LABELS, useAuth } from '../context/AuthContext'
import { BRAND } from '../theme'

const DEMO_PASSWORD = 'AgriCore2026!'
const DEMO_ACCOUNTS = [
  { email: 'admin@prairiecrest.coop', role: 'admin' },
  { email: 'farmhand@prairiecrest.coop', role: 'farm_hand' },
  { email: 'auditor@prairiecrest.coop', role: 'auditor' },
]

// The logo's tagline doubles as the product pitch.
const PILLARS = [
  { icon: <AgricultureIcon />, title: 'Equipment', text: 'Every tractor, combine, sprayer and pump across all member farms.' },
  { icon: <BuildCircleIcon />, title: 'Service', text: 'Field jobs, status updates and service reports stored in S3.' },
  { icon: <InsightsIcon />, title: 'Insight', text: 'Live answers on fuel, maintenance load and reliability.' },
]

export default function LoginPage() {
  const { login, isAuthenticated } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  if (isAuthenticated) return <Navigate to="/" replace />

  async function doLogin(e, creds) {
    e?.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(creds?.email ?? email, creds?.password ?? password)
      navigate(location.state?.from?.pathname || '/', { replace: true })
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Box sx={{ minHeight: '100vh', display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1.1fr 1fr' }, bgcolor: 'background.default' }}>
      {/* Brand panel - always white, because the logo artwork sits on white */}
      <Box
        sx={{
          bgcolor: '#ffffff',
          color: BRAND.forest,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          px: { xs: 2, sm: 4, md: 6 },
          py: { xs: 3, md: 6 },
          borderRight: { md: `6px solid ${BRAND.gold}` },
          borderBottom: { xs: `4px solid ${BRAND.gold}`, md: 'none' },
        }}
      >
        {/* mix-blend-mode: multiply melts the artwork's off-white background into the panel */}
        <Box
          component="img"
          src={LOGO_FULL}
          alt="AgriCore - Equipment. Service. Insight."
          sx={{ width: '100%', maxWidth: { xs: 240, sm: 300, md: 460 }, height: 'auto', mixBlendMode: 'multiply' }}
        />
        <Typography sx={{ mt: { xs: 1, md: 2 }, fontWeight: 800, fontSize: { xs: 18, md: 24 }, textAlign: 'center' }}>
          Smart Farm Command Center
        </Typography>
        <Typography sx={{ color: '#55625a', textAlign: 'center', maxWidth: 440, display: { xs: 'none', md: 'block' } }}>
          Prairie Crest Agricultural Cooperative · one place for shared equipment, field work and operational insight.
        </Typography>
        <Stack spacing={1.5} sx={{ mt: 4, maxWidth: 460, width: '100%', display: { xs: 'none', md: 'flex' } }}>
          {PILLARS.map((p) => (
            <Box key={p.title} sx={{ display: 'flex', gap: 1.5, alignItems: 'flex-start' }}>
              <Box sx={{ color: BRAND.green, display: 'flex', mt: '2px' }}>{p.icon}</Box>
              <Box>
                <Typography sx={{ fontWeight: 700, lineHeight: 1.3 }}>{p.title}</Typography>
                <Typography variant="body2" sx={{ color: '#55625a' }}>{p.text}</Typography>
              </Box>
            </Box>
          ))}
        </Stack>
      </Box>

      {/* Sign-in panel */}
      <Box sx={{ display: 'grid', placeItems: 'center', px: 2, py: { xs: 3, md: 6 } }}>
        <Card sx={{ width: '100%', maxWidth: 420 }}>
          <CardContent sx={{ p: { xs: 3, sm: 4 } }}>
            <Typography variant="h5">Sign in</Typography>
            <Typography color="text.secondary" sx={{ mb: 3 }}>
              Use your cooperative account or a demo role below.
            </Typography>
            <form onSubmit={doLogin}>
              <Stack spacing={2}>
                {error && <Alert severity="error">{error}</Alert>}
                <TextField label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" required />
                <TextField label="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
                <Button type="submit" variant="contained" size="large" disabled={busy}>
                  Sign in
                </Button>
              </Stack>
            </form>
            <Divider sx={{ my: 3 }}>Demo accounts</Divider>
            <Stack spacing={1}>
              {DEMO_ACCOUNTS.map((a) => (
                <Button
                  key={a.email}
                  variant="outlined"
                  disabled={busy}
                  onClick={() => doLogin(null, { email: a.email, password: DEMO_PASSWORD })}
                  sx={{ justifyContent: 'space-between', gap: 1, flexWrap: 'wrap' }}
                >
                  <span>{ROLE_LABELS[a.role]}</span>
                  <Typography variant="caption" color="text.secondary" sx={{ display: { xs: 'none', sm: 'inline' } }}>{a.email}</Typography>
                </Button>
              ))}
            </Stack>
          </CardContent>
        </Card>
      </Box>
    </Box>
  )
}
