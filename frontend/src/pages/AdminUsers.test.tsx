import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AdminUsers from './AdminUsers'
import { getUsers, resetUserPassword } from '../api/client'
import type { AuthUser } from '../api/types'

vi.mock('../api/client', () => ({
  getUsers: vi.fn(),
  inviteUser: vi.fn(),
  updateUser: vi.fn(),
  resetUserPassword: vi.fn(),
}))

const admin: AuthUser = {
  id: 1,
  username: 'admin',
  role: 'admin',
  is_active: true,
  created_at: null,
  last_login_at: null,
}

describe('AdminUsers', () => {
  beforeEach(() => {
    vi.mocked(getUsers).mockReset()
    vi.mocked(resetUserPassword).mockReset()
  })

  it('resets a password via the modal and shows a toast', async () => {
    vi.mocked(getUsers).mockResolvedValue([admin])
    vi.mocked(resetUserPassword).mockResolvedValue({ status: 'ok' })

    render(<AdminUsers />)

    fireEvent.click(
      await screen.findByRole('button', { name: 'Сбросить пароль: admin' }),
    )
    fireEvent.change(await screen.findByLabelText('Новый пароль'), {
      target: { value: 'new-secret' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }))

    expect(
      await screen.findByText('Пароль для admin успешно сброшен'),
    ).toBeInTheDocument()
    expect(resetUserPassword).toHaveBeenCalledWith(1, 'new-secret')
  })
})
