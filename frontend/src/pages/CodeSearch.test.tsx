import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import CodeSearch from './CodeSearch'
import { getCodeSearchStatus, searchCode } from '../api/client'

vi.mock('../api/client', () => ({
  getCodeSearchStatus: vi.fn(),
  indexCode: vi.fn(),
  searchCode: vi.fn(),
}))

describe('CodeSearch', () => {
  beforeEach(() => {
    vi.mocked(getCodeSearchStatus).mockReset()
    vi.mocked(searchCode).mockReset()
  })

  it('shows an info banner and disables actions when RAG is unavailable', async () => {
    vi.mocked(getCodeSearchStatus).mockRejectedValue(
      new Error('503 rag_unavailable'),
    )

    render(<CodeSearch />)

    fireEvent.change(await screen.findByLabelText('Поиск по коду (RAG)…'), {
      target: { value: 'redis' },
    })

    expect(
      await screen.findByText('Поиск по коду недоступен. Проверьте настройки БД'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Найти' })).toBeDisabled()
    expect(
      screen.getByRole('button', { name: 'Запустить индексацию (RAG)' }),
    ).toBeDisabled()
  })

  it('keeps actions enabled when the index status is available', async () => {
    vi.mocked(getCodeSearchStatus).mockResolvedValue({
      indexed_repositories: 1,
      indexed_chunks: 10,
      last_indexed_at: null,
      running: false,
      errors: [],
    })

    render(<CodeSearch />)

    await screen.findByText(/Проиндексировано: 10/)
    fireEvent.change(screen.getByLabelText('Поиск по коду (RAG)…'), {
      target: { value: 'redis' },
    })
    expect(screen.getByRole('button', { name: 'Найти' })).not.toBeDisabled()
    expect(
      screen.getByRole('button', { name: 'Запустить индексацию (RAG)' }),
    ).not.toBeDisabled()
  })

  it('points to AI provider settings when the embedding model is unavailable', async () => {
    vi.mocked(getCodeSearchStatus).mockResolvedValue({
      indexed_repositories: 1,
      indexed_chunks: 10,
      last_indexed_at: null,
      running: false,
      errors: [],
    })
    vi.mocked(searchCode).mockRejectedValue(
      new Error(
        '503 embedding_model_unavailable: проверьте настройки AI-провайдера',
      ),
    )

    render(<CodeSearch />)

    await screen.findByText(/Проиндексировано: 10/)
    fireEvent.change(screen.getByLabelText('Поиск по коду (RAG)…'), {
      target: { value: 'redis' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Найти' }))

    expect(
      await screen.findByText(/Модель эмбеддингов недоступна/),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/Настройки → AI Провайдеры/),
    ).toBeInTheDocument()
  })
})
