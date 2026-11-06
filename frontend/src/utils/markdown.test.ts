import { describe, expect, it } from 'vitest'

import type { DashboardRepository, DashboardSummary } from '../api/types'
import { buildDashboardMarkdown } from './markdown'

const summary: DashboardSummary = {
  total: 2,
  clean: 1,
  needs_attention: 1,
  untracked: 0,
  stale: 0,
  errors: 0,
  mirror_issues: 1,
  by_state: { current: 1, diverged: 1 },
  by_mirror_status: { behind_gitflic: 1 },
}

function makeRepo(
  overrides: Partial<DashboardRepository> = {},
): DashboardRepository {
  return {
    id: 1,
    path: 'C:/work/alpha',
    alias: 'alpha',
    tracked: true,
    github_full_name: 'acme/alpha',
    gitflic_full_name: 'acme/alpha',
    canonical_provider: 'github',
    mirror_expected: true,
    mirror_policy: 'github_to_gitflic',
    created_at: '2026-11-01T00:00:00Z',
    updated_at: '2026-11-01T00:00:00Z',
    status: {
      repository_id: 1,
      path: 'C:/work/alpha',
      branch: 'main',
      head_sha: 'abc123',
      head_subject: 'feat',
      head_date: '2026-11-05T10:00:00Z',
      upstream: 'origin/main',
      ahead: 2,
      behind: 5,
      state: 'diverged',
      dirty: { modified: 0, staged: 0, untracked: 0, conflicted: 0 },
      detached: false,
      remote_status: 'ok',
      error: null,
      checked_at: '2026-11-05T10:00:00Z',
    },
    mirror: {
      repository_id: 1,
      github: null,
      gitflic: null,
      mirror_status: 'behind_gitflic',
      canonical_provider: 'github',
      mirror_expected: true,
      recommendations: [],
      checked_at: '2026-11-05T10:00:00Z',
    },
    ...overrides,
  }
}

describe('buildDashboardMarkdown', () => {
  it('renders counts and attention projects', () => {
    const markdown = buildDashboardMarkdown({
      summary,
      repositories: [makeRepo()],
      generatedAt: new Date('2026-11-06T12:00:00Z'),
    })

    expect(markdown).toContain('## IIRuchating Summary (2026-11-06)')
    expect(markdown).toContain('- Всего репозиториев: 2')
    expect(markdown).toContain(
      '- Требуют внимания: 1 (dirty, ahead, behind)',
    )
    expect(markdown).toContain('- Зеркала расходятся: 1')
    expect(markdown).toContain(
      '- **alpha** (`C:/work/alpha`): diverged (2 ahead, 5 behind) — [Mirror: behind_gitflic]',
    )
  })

  it('reports when there are no problem projects', () => {
    const markdown = buildDashboardMarkdown({
      summary: { ...summary, needs_attention: 0 },
      repositories: [
        makeRepo({
          status: { ...makeRepo().status!, state: 'current', ahead: 0, behind: 0 },
          mirror: null,
        }),
      ],
      generatedAt: new Date('2026-11-06T12:00:00Z'),
    })

    expect(markdown).toContain('_Проблемных проектов нет._')
  })

  it('escapes markdown control characters in names and paths', () => {
    const markdown = buildDashboardMarkdown({
      summary: { ...summary, total: 1, needs_attention: 1 },
      repositories: [
        makeRepo({
          alias: 'my_*project*',
          path: 'C:/work/my`project',
        }),
      ],
      generatedAt: new Date('2026-11-06T12:00:00Z'),
    })

    expect(markdown).toContain('**my\\_\\*project\\***')
    expect(markdown).toContain('`C:/work/my\'project`')
  })
})
