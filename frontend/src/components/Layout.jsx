import AgricultureIcon from '@mui/icons-material/Agriculture'
import AssignmentIcon from '@mui/icons-material/Assignment'
import DashboardIcon from '@mui/icons-material/Dashboard'
import GroupIcon from '@mui/icons-material/Group'
import HistoryIcon from '@mui/icons-material/History'
import LogoutIcon from '@mui/icons-material/Logout'
import MenuIcon from '@mui/icons-material/Menu'
import WarehouseIcon from '@mui/icons-material/Warehouse'
import {
  AppBar,
  Box,
  Button,
  Chip,
  Container,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
} from '@mui/material'
import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { ROLE_LABELS, useAuth } from '../context/AuthContext'
import { BrandBadge, Wordmark } from './Brand'

const DRAWER_WIDTH = 232

// Each nav item lists the roles that may see it.
const NAV = [
  { to: '/', label: 'Dashboard', icon: <DashboardIcon />, roles: ['admin', 'auditor', 'farm_hand'] },
  { to: '/equipment', label: 'Equipment', icon: <AgricultureIcon />, roles: ['admin', 'auditor', 'farm_hand'] },
  { to: '/jobs', label: 'Field Jobs', icon: <AssignmentIcon />, roles: ['admin', 'auditor', 'farm_hand'] },
  { to: '/farms', label: 'Farms', icon: <WarehouseIcon />, roles: ['admin', 'auditor', 'farm_hand'] },
  { to: '/users', label: 'Users', icon: <GroupIcon />, roles: ['admin', 'auditor'] },
  { to: '/audit', label: 'Audit Log', icon: <HistoryIcon />, roles: ['admin', 'auditor'] },
]

export default function Layout() {
  const { user, logout, hasRole } = useAuth()
  const [mobileOpen, setMobileOpen] = useState(false)

  const drawer = (
    <Box>
      <Box sx={{ px: 2, pt: 2.5, pb: 2, borderBottom: 1, borderColor: 'divider', mb: 1 }}>
        <Wordmark width={196} />
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1, fontWeight: 700, fontSize: 11, letterSpacing: '0.04em', textTransform: 'uppercase', whiteSpace: 'nowrap' }}>
          Smart Farm Command Center
        </Typography>
      </Box>
      <List sx={{ px: 1 }}>
        {NAV.filter((item) => hasRole(...item.roles)).map((item) => (
          <ListItemButton
            key={item.to}
            component={NavLink}
            to={item.to}
            end={item.to === '/'}
            onClick={() => setMobileOpen(false)}
            sx={{ borderRadius: 2, mb: 0.5, '&.active': { bgcolor: 'action.selected', color: 'primary.main' } }}
          >
            <ListItemIcon sx={{ minWidth: 36, color: 'inherit' }}>{item.icon}</ListItemIcon>
            <ListItemText primary={item.label} />
          </ListItemButton>
        ))}
      </List>
    </Box>
  )

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', bgcolor: 'background.default' }}>
      <AppBar
        position="fixed"
        color="inherit"
        elevation={0}
        sx={{ borderBottom: 1, borderColor: 'divider', width: { md: `calc(100% - ${DRAWER_WIDTH}px)` }, ml: { md: `${DRAWER_WIDTH}px` } }}
      >
        <Toolbar sx={{ gap: 1 }}>
          <IconButton edge="start" onClick={() => setMobileOpen(true)} sx={{ display: { md: 'none' } }}>
            <MenuIcon />
          </IconButton>
          <BrandBadge size={34} sx={{ display: { md: 'none' } }} />
          <Typography variant="subtitle1" fontWeight={700} sx={{ flexGrow: 1 }} noWrap>
            Prairie Crest Cooperative
          </Typography>
          <Box sx={{ display: { xs: 'none', sm: 'flex' }, alignItems: 'center', gap: 1 }}>
            <Typography variant="body2">{user.full_name}</Typography>
            <Chip size="small" color="primary" variant="outlined" label={ROLE_LABELS[user.role]} />
          </Box>
          <Button color="inherit" startIcon={<LogoutIcon />} onClick={logout} sx={{ display: { xs: 'none', sm: 'inline-flex' } }}>
            Sign out
          </Button>
          <IconButton aria-label="Sign out" onClick={logout} sx={{ display: { sm: 'none' } }}>
            <LogoutIcon />
          </IconButton>
        </Toolbar>
      </AppBar>

      <Box component="nav" sx={{ width: { md: DRAWER_WIDTH }, flexShrink: { md: 0 } }}>
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={() => setMobileOpen(false)}
          sx={{ display: { xs: 'block', md: 'none' }, '& .MuiDrawer-paper': { width: DRAWER_WIDTH } }}
        >
          {drawer}
        </Drawer>
        <Drawer
          variant="permanent"
          open
          sx={{ display: { xs: 'none', md: 'block' }, '& .MuiDrawer-paper': { width: DRAWER_WIDTH, boxSizing: 'border-box' } }}
        >
          {drawer}
        </Drawer>
      </Box>

      <Box component="main" sx={{ flexGrow: 1, minWidth: 0 }}>
        <Toolbar />
        <Container maxWidth="xl" sx={{ py: 3, px: { xs: 2, sm: 3 } }}>
          {/* The matched child route renders here */}
          <Outlet />
        </Container>
      </Box>
    </Box>
  )
}
