import { Suspense, lazy, useEffect, useRef, useState } from 'react'
import { Outlet, Route, Routes, useLocation, useNavigate } from 'react-router-dom'

import { getSettingsStatus } from './api/client'
import AdminRoute from './components/AdminRoute'
import AppLayout from './components/AppLayout'
import ProtectedRoute from './components/ProtectedRoute'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const RepositoryDetails = lazy(() => import('./pages/RepositoryDetails'))
const Settings = lazy(() => import('./pages/Settings'))
const CodeSearch = lazy(() => import('./pages/CodeSearch'))
const Login = lazy(() => import('./pages/Login'))
const Onboarding = lazy(() => import('./pages/Onboarding'))
const AdminUsers = lazy(() => import('./pages/AdminUsers'))
const AdminAudit = lazy(() => import('./pages/AdminAudit'))

function OnboardingGate() {
  const location = useLocation()
  const navigate = useNavigate()
  const initialPath = useRef(location.pathname)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const controller = new AbortController()

    void getSettingsStatus()
      .then((status) => {
        if (controller.signal.aborted || status.is_configured) {
          return
        }
        if (initialPath.current !== '/onboarding') {
          navigate('/onboarding', { replace: true })
        }
      })
      .catch(() => {
        // Backend may still be warming up; keep the normal UI.
      })
      .finally(() => {
        if (!controller.signal.aborted) setReady(true)
      })

    return () => controller.abort()
    // Check once per app start; later navigation must not re-open the wizard.
  }, [navigate])

  if (!ready) {
    return <p className="text-sm text-slate-500 dark:text-slate-400">Загрузка…</p>
  }

  return <Outlet />
}

export default function App() {
  return (
    <Suspense fallback={<p className="text-sm text-slate-500">Загрузка…</p>}>
      <Routes>
        <Route path="login" element={<Login />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<OnboardingGate />}>
            <Route path="onboarding" element={<Onboarding />} />
            <Route element={<AppLayout />}>
              <Route index element={<Dashboard />} />
              <Route path="repo/:id" element={<RepositoryDetails />} />
              <Route path="search" element={<CodeSearch />} />
              <Route path="settings" element={<Settings />} />
              <Route element={<AdminRoute />}>
                <Route path="admin/users" element={<AdminUsers />} />
                <Route path="admin/audit" element={<AdminAudit />} />
              </Route>
            </Route>
          </Route>
        </Route>
      </Routes>
    </Suspense>
  )
}
