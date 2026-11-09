import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { chatWithCode } from '../api/client'
import { LanguageProvider, useI18nNamespace } from '../i18n'
import CodeChat from './CodeChat'

vi.mock('../api/client', () => ({
  chatWithCode: vi.fn(),
}))

function ReadyChat() {
  const ready = useI18nNamespace('search')
  return ready ? <CodeChat /> : null
}

function renderChat() {
  return render(
    <LanguageProvider>
      <MemoryRouter>
        <ReadyChat />
      </MemoryRouter>
    </LanguageProvider>,
  )
}

describe('CodeChat', () => {
  beforeEach(() => {
    window.localStorage.setItem('iiruchating.locale', 'ru')
    vi.clearAllMocks()
    vi.mocked(chatWithCode).mockResolvedValue({
      answer: 'Redis используется в проекте demo.',
      sources: ['demo/src/redis.py:10-20'],
      citations: [
        {
          repository_id: 3,
          repository_name: 'demo',
          path: 'src/redis.py',
          start_line: 10,
          end_line: 20,
          language: 'python',
          snippet: "REDIS_URL = 'redis://localhost'",
          score: 0.91,
          url: null,
        },
      ],
      model: 'fake-model',
      embedding_model: 'fake-embed',
      took_ms: 42,
    })
  })

  it('sends a question and renders the answer with a source link', async () => {
    const user = userEvent.setup()
    renderChat()

    await user.type(
      await screen.findByPlaceholderText('Спросите о кодовой базе…'),
      'где используется Redis?',
    )
    await user.click(screen.getByRole('button', { name: 'Отправить' }))

    expect(
      await screen.findByText('Redis используется в проекте demo.'),
    ).toBeInTheDocument()
    expect(chatWithCode).toHaveBeenCalledWith({
      query: 'где используется Redis?',
      history: [],
      limit: 5,
      min_score: 0.2,
    })
    expect(screen.getByRole('link', { name: 'demo/src/redis.py:10' })).toHaveAttribute(
      'href',
      '/repo/3',
    )
  })
})
