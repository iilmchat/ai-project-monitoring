import type { Page, Route } from '@playwright/test'

export interface ApiMockOptions {
  /** Show the repository in the dashboard before a scan finishes. */
  hasRepositoriesBeforeScan?: boolean
  /** Report dirty working tree and enable the AI commit button. */
  dirty?: boolean
  /** Value of `llm_enabled` returned by GET /settings. */
  llmEnabled?: boolean
  /** Message returned by the mocked LLM endpoint. */
  commitMessage?: string
}

const NOW = '2026-11-08T10:00:00Z'

const repository = {
  id: 1,
  path: 'C:/work/alpha',
  alias: 'alpha',
  tracked: true,
  github_full_name: 'octocat/alpha',
  gitflic_full_name: null,
  canonical_provider: 'github',
  mirror_expected: false,
  mirror_policy: 'manual',
  created_at: NOW,
  updated_at: NOW,
}

function status(dirty: boolean) {
  return {
    repository_id: 1,
    path: repository.path,
    branch: 'main',
    head_sha: 'a'.repeat(40),
    head_subject: 'Initial commit',
    head_date: NOW,
    upstream: 'origin/main',
    ahead: 0,
    behind: 0,
    state: dirty ? 'dirty' : 'current',
    dirty: {
      modified: dirty ? 2 : 0,
      staged: 0,
      untracked: 0,
      conflicted: 0,
    },
    detached: false,
    remote_status: 'ok',
    error: null,
    checked_at: NOW,
  }
}

function dashboardResponse(hasRepository: boolean, dirty: boolean) {
  return {
    summary: {
      total: hasRepository ? 1 : 0,
      clean: hasRepository && !dirty ? 1 : 0,
      needs_attention: hasRepository && dirty ? 1 : 0,
      untracked: 0,
      stale: 0,
      errors: 0,
      mirror_issues: 0,
      by_state: hasRepository ? { [dirty ? 'dirty' : 'current']: 1 } : {},
      by_mirror_status: {},
    },
    repositories: hasRepository
      ? [{ ...repository, status: status(dirty), mirror: null, ci: null }]
      : [],
  }
}

const mirrorStatus = {
  repository_id: 1,
  github: null,
  gitflic: null,
  mirror_status: 'unavailable',
  canonical_provider: 'github',
  mirror_expected: false,
  recommendations: [],
  checked_at: NOW,
}

const ciStatus = {
  repository_id: 1,
  branch: 'main',
  github: { provider: 'github', status: 'unknown', conclusion: null, url: null },
  gitflic: { provider: 'gitflic', status: 'unknown', conclusion: null, url: null },
  aggregate: 'unknown',
}

const dependenciesReport = {
  repository_id: 1,
  checked_at: NOW,
  ecosystems: [],
  summary: {
    total: 0,
    outdated: 0,
    up_to_date: 0,
    unknown: 0,
    ignored: 0,
  },
}

const securityReport = {
  repository_id: 1,
  checked_at: NOW,
  status: 'ok',
  summary: {
    total_packages: 0,
    packages_checked: 0,
    vulnerable: 0,
    critical: 0,
    high: 0,
    medium: 0,
    low: 0,
    unknown: 0,
    secrets_found: 0,
  },
  ecosystems: [],
  secrets: {
    status: 'ok',
    files_scanned: 0,
    truncated: false,
    findings: [],
    error: null,
  },
  error: null,
}

const insightsReport = {
  repository_id: 1,
  checked_at: NOW,
  status: 'ok',
  window: {
    days: 30,
    since: NOW,
    until: NOW,
    branch: 'main',
    hotspots_days: 30,
  },
  hotspots: [],
  commit_frequency: [],
  summary: { commits: 0, per_day: 0, per_week: 0 },
  error: null,
}

const globalDependenciesReport = {
  checked_at: NOW,
  ecosystems: { python: [], node: [] },
  summary: { repositories: 1, packages: 0, unification_candidates: 0 },
  error: null,
}

const readme = {
  repository_id: 1,
  path: 'README.md',
  name: 'alpha',
  version: '0.1.0',
  content: '# alpha',
}

const dockerStatus = {
  repository_id: 1,
  status: 'not_found',
  containers: [],
  error: null,
  checked_at: NOW,
}

const actionLog = {
  id: 1,
  repository_id: 1,
  action: 'commit',
  command: 'git commit',
  status: 'success',
  exit_code: 0,
  output: 'ok',
  error: null,
  duration_ms: 5,
  actor: 'e2e',
  created_at: NOW,
}

async function json(route: Route, body: unknown, statusCode = 200): Promise<void> {
  await route.fulfill({
    status: statusCode,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })
}

export interface ApiMockHandle {
  commitMessageRequests: () => number
  commitRequests: () => number
}

/**
 * Installs a single catch-all route that emulates every backend endpoint the
 * dashboard and repository details pages use. Tests never touch the real
 * backend or an LLM.
 */
export async function installApiMocks(
  page: Page,
  options: ApiMockOptions = {},
): Promise<ApiMockHandle> {
  let hasRepository = options.hasRepositoriesBeforeScan ?? true
  let commitMessageRequests = 0
  let commitRequests = 0
  const dirty = options.dirty ?? false
  const llmEnabled = options.llmEnabled ?? false
  const commitMessage =
    options.commitMessage ?? 'feat: mocked commit message'

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const method = request.method()
    const path = new URL(request.url()).pathname.replace('/api/v1', '')

    if (method === 'GET' && path === '/dashboard') {
      await json(route, dashboardResponse(hasRepository, dirty))
      return
    }
    if (method === 'POST' && path === '/scan') {
      hasRepository = true
      await json(route, { scan_id: 1, started_at: NOW })
      return
    }
    if (method === 'GET' && path === '/scan/1') {
      await json(route, {
        id: 1,
        status: 'completed',
        started_at: NOW,
        finished_at: NOW,
        found: 1,
        added: 1,
        skipped: 0,
        errors: [],
      })
      return
    }
    if (method === 'GET' && path === '/repositories') {
      await json(route, {
        items: [repository],
        total: 1,
        skip: 0,
        limit: 500,
      })
      return
    }
    if (method === 'GET' && path === '/settings') {
      await json(route, {
        scan_roots: '',
        github_token: '',
        gitflic_token: '',
        webhook_secret: '',
        default_canonical_provider: 'github',
        llm_enabled: llmEnabled,
        llm_base_url: 'http://127.0.0.1:1234/v1',
        llm_model: 'mock-model',
        llm_api_key: '',
        llm_timeout_seconds: 30,
        llm_max_diff_chars: 10000,
        llm_allow_remote: false,
      })
      return
    }
    if (method === 'GET' && path === '/settings/ai-providers') {
      await json(route, [])
      return
    }
    if (method === 'GET' && path === '/dashboard/global-dependencies') {
      await json(route, globalDependenciesReport)
      return
    }
    if (method === 'POST' && path === '/repositories/1/ai/commit-message') {
      commitMessageRequests += 1
      await json(route, {
        repository_id: 1,
        message: commitMessage,
        source: 'llm',
        provider: 'mock',
        model: 'mock-model',
        truncated: false,
        diff_chars: 42,
        files_changed: 1,
        warnings: [],
        generated_at: NOW,
      })
      return
    }

    const detailRoutes: Record<string, unknown> = {
      '/repositories/1/status': status(dirty),
      '/repositories/1/log': [],
      '/repositories/1/recommendations': [],
      '/repositories/1/mirror': mirrorStatus,
      '/repositories/1/actions': [],
      '/repositories/1/ci-status': ciStatus,
      '/repositories/1/conflicts': { repository_id: 1, files: [] },
      '/repositories/1/docker': dockerStatus,
      '/repositories/1/dependencies': dependenciesReport,
      '/repositories/1/security': securityReport,
      '/repositories/1/insights': insightsReport,
      '/repositories/1/readme': readme,
    }
    if (method === 'GET' && path in detailRoutes) {
      await json(route, detailRoutes[path])
      return
    }
    if (method === 'POST' && path === '/repositories/1/refresh') {
      await json(route, status(dirty))
      return
    }
    if (method === 'POST' && path === '/repositories/1/actions/commit') {
      commitRequests += 1
      await json(route, actionLog)
      return
    }

    await json(route, { detail: `No mock for ${method} ${path}` }, 404)
  })

  return {
    commitMessageRequests: () => commitMessageRequests,
    commitRequests: () => commitRequests,
  }
}
