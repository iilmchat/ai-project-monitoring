import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { generateReleaseNotes, getTags } from '../api/client'
import { LanguageProvider, useI18nNamespace } from '../i18n'
import ReleaseNotesModal from './ReleaseNotesModal'

vi.mock('../api/client', () => ({
  getTags: vi.fn(),
  generateReleaseNotes: vi.fn(),
}))

function ReadyModal() {
  const ready = useI18nNamespace('repository')
  return ready ? (
    <ReleaseNotesModal repositoryId={3} onClose={() => undefined} />
  ) : null
}

function renderModal() {
  return render(
    <LanguageProvider>
      <ReadyModal />
    </LanguageProvider>,
  )
}

describe('ReleaseNotesModal', () => {
  beforeEach(() => {
    window.localStorage.setItem('iiruchating.locale', 'ru')
    vi.clearAllMocks()
    vi.mocked(getTags).mockResolvedValue({
      repository_id: 3,
      tags: ['v1.0.0', 'v1.1.0'],
    })
    vi.mocked(generateReleaseNotes).mockResolvedValue({
      repository_id: 3,
      from_tag: 'v1.0.0',
      to_tag: 'HEAD',
      changelog: '## [1.1.0]\n### Added\n- feature',
      commits: 4,
      provider: 'fake',
      model: 'fake-model',
      truncated: false,
      warnings: [],
      cached: false,
      generated_at: '2026-11-09T12:00:00Z',
    })
  })

  it('loads tags and generates a changelog', async () => {
    const user = userEvent.setup()
    renderModal()

    expect(await screen.findByDisplayValue('v1.0.0')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Сгенерировать' }))

    expect(await screen.findByText('Added')).toBeInTheDocument()
    expect(generateReleaseNotes).toHaveBeenCalledWith(3, 'v1.0.0', 'HEAD', 'ru')
  })
})
