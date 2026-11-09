import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { reviewCode } from '../api/client'
import { LanguageProvider, useI18nNamespace } from '../i18n'
import CodeReviewModal from './CodeReviewModal'

vi.mock('../api/client', () => ({
  reviewCode: vi.fn(),
}))

function ReadyModal() {
  const ready = useI18nNamespace('repository')
  return ready ? (
    <CodeReviewModal repositoryId={7} onClose={() => undefined} />
  ) : null
}

function renderModal() {
  return render(
    <LanguageProvider>
      <ReadyModal />
    </LanguageProvider>,
  )
}

describe('CodeReviewModal', () => {
  beforeEach(() => {
    window.localStorage.setItem('iiruchating.locale', 'ru')
    vi.clearAllMocks()
    vi.mocked(reviewCode).mockResolvedValue({
      repository_id: 7,
      review: '## Найдены проблемы\n\n- `app.py:2` — проверьте обработку',
      source: 'llm',
      provider: 'fake',
      model: 'fake-model',
      files_reviewed: 1,
      diff_chars: 42,
      truncated: false,
      warnings: [],
      cached: false,
      generated_at: '2026-11-09T12:00:00Z',
    })
  })

  it('loads and renders the Markdown review', async () => {
    renderModal()

    expect(await screen.findByText('Найдены проблемы')).toBeInTheDocument()
    expect(reviewCode).toHaveBeenCalledWith(7, 'ru')
  })

  it('shows a cache notice and copies the review', async () => {
    const user = userEvent.setup()
    vi.mocked(reviewCode).mockResolvedValue({
      repository_id: 7,
      review: '## Кэш',
      source: 'llm',
      provider: 'fake',
      model: 'fake-model',
      files_reviewed: 1,
      diff_chars: 42,
      truncated: false,
      warnings: [],
      cached: true,
      generated_at: '2026-11-09T12:00:00Z',
    })
    const writeText = vi
      .spyOn(navigator.clipboard, 'writeText')
      .mockResolvedValue(undefined)

    renderModal()

    expect(
      await screen.findByText('Результат из кэша: diff не изменился.'),
    ).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Скопировать' }))

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith('## Кэш')
    })
  })
})
