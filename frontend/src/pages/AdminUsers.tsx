import { useEffect, useState } from 'react'

import { getUsers, inviteUser, updateUser } from '../api/client'
import type { AuthUser, UserRole } from '../api/types'
import { useI18n, useI18nNamespace } from '../i18n'

export default function AdminUsers() {
  const ready = useI18nNamespace('admin')
  const { t, formatDate } = useI18n()
  const [users, setUsers] = useState<AuthUser[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [inviteOpen, setInviteOpen] = useState(false)
  const [username, setUsername] = useState('')
  const [role, setRole] = useState<UserRole>('auditor')
  const [inviteError, setInviteError] = useState<string | null>(null)
  const [tempPassword, setTempPassword] = useState<string | null>(null)
  const [savingId, setSavingId] = useState<number | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    setLoading(true)
    void getUsers()
      .then((items) => {
        if (active) {
          setUsers(items)
          setError(null)
        }
      })
      .catch(() => {
        if (active) setError(t('admin.error'))
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [t])

  async function handleInvite() {
    const value = username.trim()
    if (!value) return
    setInviteError(null)
    try {
      const response = await inviteUser({ username: value, role })
      setUsers((current) => [...current, response.user])
      setTempPassword(response.temporary_password)
      setUsername('')
      setRole('auditor')
      setInviteOpen(false)
      setNotice(t('admin.invited'))
    } catch (cause) {
      const text = cause instanceof Error ? cause.message : ''
      setInviteError(
        text.includes('409') ? 'username_exists' : t('admin.error'),
      )
    }
  }

  async function handleRoleChange(user: AuthUser, nextRole: UserRole) {
    setSavingId(user.id)
    setError(null)
    try {
      const updated = await updateUser(user.id, { role: nextRole })
      setUsers((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      )
      setNotice(t('admin.roleUpdated'))
    } catch (cause) {
      const text = cause instanceof Error ? cause.message : ''
      setError(text.includes('409') ? 'last_admin' : t('admin.error'))
    } finally {
      setSavingId(null)
    }
  }

  if (!ready) {
    return <p className="text-sm text-slate-500">{t('common.loading')}</p>
  }

  return (
    <section className="space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">
            {t('admin.usersTitle')}
          </h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-500 dark:text-slate-400">
            {t('admin.usersSubtitle')}
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            setInviteOpen((value) => !value)
            setInviteError(null)
          }}
          className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-white hover:opacity-90"
        >
          {t('admin.invite')}
        </button>
      </header>

      {notice && (
        <p className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-200">
          {notice}
        </p>
      )}
      {tempPassword && (
        <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-900/30 dark:text-amber-100">
          <p>{t('admin.temporaryPassword')}</p>
          <code className="mt-1 block font-mono text-base">{tempPassword}</code>
        </div>
      )}

      {inviteOpen && (
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900">
          <div className="grid gap-3 sm:grid-cols-[1fr_180px_auto]">
            <label className="text-sm">
              <span className="mb-1 block text-slate-600 dark:text-slate-300">
                {t('admin.username')}
              </span>
              <input
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                className="w-full rounded-md border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-800"
                autoComplete="off"
              />
            </label>
            <label className="text-sm">
              <span className="mb-1 block text-slate-600 dark:text-slate-300">
                {t('admin.role')}
              </span>
              <select
                value={role}
                onChange={(event) => setRole(event.target.value as UserRole)}
                className="w-full rounded-md border border-slate-300 px-3 py-2 dark:border-slate-600 dark:bg-slate-800"
              >
                <option value="auditor">{t('admin.auditor')}</option>
                <option value="admin">{t('admin.admin')}</option>
              </select>
            </label>
            <div className="flex items-end gap-2">
              <button
                type="button"
                onClick={() => void handleInvite()}
                disabled={!username.trim()}
                className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
              >
                {t('admin.create')}
              </button>
              <button
                type="button"
                onClick={() => setInviteOpen(false)}
                className="rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-600"
              >
                {t('admin.cancel')}
              </button>
            </div>
          </div>
          {inviteError && (
            <p className="mt-2 text-sm text-red-700 dark:text-red-300">
              {inviteError}
            </p>
          )}
        </div>
      )}

      {error && (
        <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200">
          {error}
        </p>
      )}

      {loading ? (
        <p className="text-sm text-slate-500">{t('admin.loading')}</p>
      ) : users.length === 0 ? (
        <p className="text-sm text-slate-500">{t('admin.empty')}</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500 dark:bg-slate-800/60 dark:text-slate-400">
              <tr>
                <th className="px-4 py-3">{t('admin.username')}</th>
                <th className="px-4 py-3">{t('admin.role')}</th>
                <th className="px-4 py-3">{t('admin.status')}</th>
                <th className="px-4 py-3">{t('admin.createdAt')}</th>
                <th className="px-4 py-3">{t('admin.lastLogin')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
              {users.map((user) => (
                <tr key={user.id}>
                  <td className="px-4 py-3 font-mono text-slate-800 dark:text-slate-200">
                    {user.username}
                  </td>
                  <td className="px-4 py-3">
                    <select
                      value={user.role}
                      disabled={savingId === user.id}
                      onChange={(event) =>
                        void handleRoleChange(
                          user,
                          event.target.value as UserRole,
                        )
                      }
                      aria-label={t('admin.role')}
                      className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm dark:border-slate-600 dark:bg-slate-800"
                    >
                      <option value="auditor">{t('admin.auditor')}</option>
                      <option value="admin">{t('admin.admin')}</option>
                    </select>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        user.is_active
                          ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200'
                          : 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-200'
                      }`}
                    >
                      {user.is_active ? t('admin.active') : t('admin.inactive')}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-600 dark:text-slate-300">
                    {formatDate(user.created_at)}
                  </td>
                  <td className="px-4 py-3 text-slate-600 dark:text-slate-300">
                    {formatDate(user.last_login_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
