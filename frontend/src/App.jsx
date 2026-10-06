import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import { RequireAuth, RequireRole } from './components/RouteGuards'
import AuditLogPage from './pages/AuditLogPage'
import DashboardPage from './pages/DashboardPage'
import EquipmentPage from './pages/EquipmentPage'
import FarmsPage from './pages/FarmsPage'
import JobsPage from './pages/JobsPage'
import LoginPage from './pages/LoginPage'
import UsersPage from './pages/UsersPage'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth><Layout /></RequireAuth>}>
        <Route index element={<DashboardPage />} />
        <Route path="equipment" element={<EquipmentPage />} />
        <Route path="jobs" element={<JobsPage />} />
        <Route path="farms" element={<FarmsPage />} />
        <Route path="users" element={<RequireRole roles={['admin', 'auditor']}><UsersPage /></RequireRole>} />
        <Route path="audit" element={<RequireRole roles={['admin', 'auditor']}><AuditLogPage /></RequireRole>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
