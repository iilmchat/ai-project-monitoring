import { Navigate, Outlet } from 'react-router-dom'

import { useAuthStore } from '../store/useAuthStore'

/** Client-side guard for admin-only pages; the API enforces the same rule. */
export default function AdminRoute() {
  const user = useAuthStore((state) => state.user)
  if (user?.role !== 'admin') {
    return <Navigate to="/" replace />
  }
  return <Outlet />
}
