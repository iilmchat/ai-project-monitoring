import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { resolveConflict } from '../api/client'
import { LanguageProvider, useI18nNamespace } from '../i18n'
import ConflictResolverModal from './ConflictResolverModal'

vi.mock('../api/client', () => ({
  resolveConflict: vi.fn(),
}))

function ReadyModal() {
  const ready = useI18nNamespace('repository')
  return ready ? (
    <ConflictResolverModal
      repositoryId={3}
      filePath="src/app.ts"
      onClose={() => undefined}
    />
  ) : null
}

function renderModal() {
  return render(
    <LanguageProvider>
      <ReadyModal />
    </LanguageProvider>,
  )
}

describe('ConflictResolverModal', () => {
  beforeEach(() => {
    window.localStorage.setItem('iiruchating.locale', 'ru')
    vi.clearAllMocks()
    vi.mocked(resolveConflict).mockResolvedValue({
      repository_id: 3,
      file_path: 'src/app.ts',
      resolved: 'const merged = true',
      blocks: 1,
      provider: 'fake',
      model: 'fake-model',
      truncated: false,
      warnings: ['verify_before_apply'],
      cached: false,
      generated_at: '2026-11-09T12:00:00Z',
    })
  })

  it('loads and renders the merged code', async () => {
    renderModal()

    expect(await screen.findByText(/const merged = true/)).toBeInTheDocument()
    expect(resolveConflict).toHaveBeenCalledWith(3, 'src/app.ts', 'ru')
    expect(
      screen.getByText(/LLM может ошибаться/),
    ).toBeInTheDocument()
  })
})
