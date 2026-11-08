import { useEffect } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { useI18n } from '../i18n'
import { useAuthStore } from '../store/useAuthStore'

export default function ProtectedRoute() {
  const { t } = useI18n()
  const location = useLocation()
  const { user, loading, checkAuth } = useAuthStore()

  useEffect(() => {
    void checkAuth()
  }, [checkAuth])

  if (loading && !user) {
    return <p className="text-sm text-slate-500 dark:text-slate-400">{t('common.loading')}</p>
  }
  if (!user) {
    const next = `${location.pathname}${location.search}`
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />
  }
  return <Outlet />
}
