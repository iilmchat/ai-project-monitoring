import { Suspense, lazy } from 'react'
import { Route, Routes } from 'react-router-dom'

import AppLayout from './components/AppLayout'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const RepositoryDetails = lazy(() => import('./pages/RepositoryDetails'))
const Settings = lazy(() => import('./pages/Settings'))
const CodeSearch = lazy(() => import('./pages/CodeSearch'))

export default function App() {
  return (
    <Suspense fallback={<p className="text-sm text-slate-500">Загрузка…</p>}>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="repo/:id" element={<RepositoryDetails />} />
          <Route path="search" element={<CodeSearch />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </Suspense>
  )
}
