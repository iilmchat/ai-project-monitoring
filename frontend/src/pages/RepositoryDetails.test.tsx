import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  getActions,
  getCiStatus,
  getConflicts,
  getDependencies,
  getDockerStatus,
  getGlobalDependencies,
  getInsights,
  getLog,
  getMirror,
  getReadme,
  getRecommendations,
  getRepositories,
  getSecurity,
  getSettings,
  getStatus,
  generateCommitMessage,
  explainCve,
  refreshRepository,
  runAction,
  updateDependencies,
} from '../api/client'
import type {
  AppSettings,
  DashboardRepository,
  DependencyReport,
  DockerStatus,
  InsightsReport,
  MirrorStatus,
  RepositoryStatus,
  SecurityReport,
} from '../api/types'
import { ThemeProvider } from '../theme/ThemeContext'
import RepositoryDetails from './RepositoryDetails'

vi.mock('../api/client', () => ({
  getActions: vi.fn(),
  getCiStatus: vi.fn(),
  getConflicts: vi.fn(),
  getDependencies: vi.fn(),
  getDockerStatus: vi.fn(),
  getGlobalDependencies: vi.fn(),
  getInsights: vi.fn(),
  getLog: vi.fn(),
  getMirror: vi.fn(),
  getReadme: vi.fn(),
  getRecommendations: vi.fn(),
  getRepositories: vi.fn(),
  getSecurity: vi.fn(),
  getSettings: vi.fn(),
  getStatus: vi.fn(),
  generateCommitMessage: vi.fn(),
  explainCve: vi.fn(),
  refreshMirror: vi.fn(),
  refreshRepository: vi.fn(),
  runAction: vi.fn(),
  runMirrorAction: vi.fn(),
  updateDependencies: vi.fn(),
  updateMirrorPolicy: vi.fn(),
}))

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: ReactNode }) => (
    <div>{children}</div>
  ),
  AreaChart: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  Area: () => <div data-testid="area" />,
  Tooltip: () => null,
  XAxis: () => null,
  YAxis: () => null,
}))

const status: RepositoryStatus = {
  repository_id: 1,
  path: 'C:/work/app',
  branch: 'main',
  head_sha: 'abc123',
  head_subject: 'init',
  head_date: '2026-11-05T10:00:00Z',
  upstream: 'origin/main',
  ahead: 0,
  behind: 0,
  state: 'dirty',
  dirty: { modified: 1, staged: 0, untracked: 0, conflicted: 0 },
  detached: false,
  remote_status: 'stale',
  error: null,
  checked_at: '2026-11-05T10:00:00Z',
}

const repository: DashboardRepository = {
  id: 1,
  path: 'C:/work/app',
  alias: 'app',
  tracked: true,
  github_full_name: 'acme/app',
  gitflic_full_name: 'acme/app',
  canonical_provider: 'github',
  mirror_expected: true,
  mirror_policy: 'github_to_gitflic',
  created_at: '2026-11-01T00:00:00Z',
  updated_at: '2026-11-01T00:00:00Z',
  status,
  mirror: null,
}

const mirror: MirrorStatus = {
  repository_id: 1,
  github: null,
  gitflic: null,
  mirror_status: 'unavailable',
  canonical_provider: 'github',
  mirror_expected: true,
  recommendations: [],
  checked_at: '2026-11-05T10:00:00Z',
}

const dockerUnavailable: DockerStatus = {
  repository_id: 1,
  status: 'unavailable',
  containers: [],
  error: 'Docker daemon not running',
  checked_at: '2026-11-05T10:00:00Z',
}

const dependenciesNoManifest: DependencyReport = {
  repository_id: 1,
  checked_at: '2026-11-05T10:00:00Z',
  ecosystems: [
    {
      ecosystem: 'python',
      manifest: 'requirements.txt',
      status: 'no_manifest',
      source: 'none',
      total: 0,
      outdated: 0,
      up_to_date: 0,
      unknown: 0,
      ignored: 0,
      packages: [],
      error: null,
    },
  ],
  summary: { total: 0, outdated: 0, up_to_date: 0, unknown: 0, ignored: 0 },
}

const cleanSecurity: SecurityReport = {
  repository_id: 1,
  checked_at: '2026-11-06T10:00:00Z',
  status: 'ok',
  summary: {
    total_packages: 1,
    packages_checked: 1,
    vulnerable: 0,
    critical: 0,
    high: 0,
    medium: 0,
    low: 0,
    unknown: 0,
    secrets_found: 0,
  },
  ecosystems: [
    {
      ecosystem: 'python',
      manifest: 'requirements.txt',
      status: 'ok',
      total_packages: 1,
      packages_checked: 1,
      vulnerabilities: [],
      unknown_packages: [],
      error: null,
    },
    {
      ecosystem: 'node',
      manifest: 'package.json',
      status: 'no_manifest',
      total_packages: 0,
      packages_checked: 0,
      vulnerabilities: [],
      unknown_packages: [],
      error: null,
    },
  ],
  secrets: {
    status: 'ok',
    files_scanned: 4,
    truncated: false,
    findings: [],
    error: null,
  },
  error: null,
}

const cleanInsights: InsightsReport = {
  repository_id: 1,
  checked_at: '2026-11-06T10:00:00Z',
  status: 'ok',
  window: {
    days: 30,
    since: '2026-10-08',
    until: '2026-11-06',
    branch: 'main',
    hotspots_days: 90,
  },
  hotspots: [],
  commit_frequency: Array.from({ length: 30 }, (_, index) => ({
    date: `2026-10-${String(index + 1).padStart(2, '0')}`,
    count: 0,
  })),
  summary: { commits: 0, per_day: 0, per_week: 0 },
  error: null,
}

const appSettings: AppSettings = {
  scan_roots: '',
  github_token: '',
  gitflic_token: '',
  webhook_secret: '',
  default_canonical_provider: 'github',
  llm_enabled: false,
  llm_base_url: 'http://127.0.0.1:1234/v1',
  llm_model: 'qwen2.5-coder-7b-instruct',
  llm_api_key: '',
  llm_timeout_seconds: 30,
  llm_max_diff_chars: 10000,
  llm_allow_remote: false,
  telegram_bot_token: '',
  telegram_chat_id: '',
  notifications_enabled: true,
  fetch_timeout: 30,
  status_ttl_seconds: 60,
  mirror_poll_interval_seconds: 300,
}

function renderDetails() {
  return render(
    <ThemeProvider>
      <MemoryRouter initialEntries={['/repo/1']}>
        <Routes>
          <Route path="/repo/:id" element={<RepositoryDetails />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>,
  )
}

describe('RepositoryDetails actions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getRepositories).mockResolvedValue({
      items: [repository],
      total: 1,
      skip: 0,
      limit: 500,
    })
    vi.mocked(getStatus).mockResolvedValue(status)
    vi.mocked(getLog).mockResolvedValue([])
    vi.mocked(getRecommendations).mockResolvedValue([
      {
        action: 'stash',
        reason: 'Есть незакоммиченные изменения.',
        command: 'git stash',
        category: 'local',
      },
    ])
    vi.mocked(getMirror).mockResolvedValue(mirror)
    vi.mocked(getReadme).mockResolvedValue({
      repository_id: 1,
      path: 'README.md',
      name: 'Demo repository',
      version: 'v1.0.0',
      content: '# Demo repository\n\nVersion: v1.0.0\n',
    })
    vi.mocked(getActions).mockResolvedValue([])
    vi.mocked(getConflicts).mockResolvedValue({ repository_id: 1, files: [] })
    vi.mocked(getDockerStatus).mockResolvedValue(dockerUnavailable)
    vi.mocked(getDependencies).mockResolvedValue(dependenciesNoManifest)
    vi.mocked(getGlobalDependencies).mockResolvedValue({
      checked_at: '2026-11-08T10:00:00Z',
      ecosystems: { python: [], node: [] },
      summary: { repositories: 0, packages: 0, unification_candidates: 0 },
      error: null,
    })
    vi.mocked(getSecurity).mockResolvedValue(cleanSecurity)
    vi.mocked(getInsights).mockResolvedValue(cleanInsights)
    vi.mocked(getSettings).mockResolvedValue(appSettings)
    vi.mocked(refreshRepository).mockResolvedValue(status)
    vi.mocked(updateDependencies).mockResolvedValue({
      id: 99,
      repository_id: 1,
      action: 'update-dependencies',
      command: 'pip install -r requirements.txt --upgrade',
      status: 'success',
      exit_code: 0,
      output: 'Successfully installed',
      error: null,
      duration_ms: 100,
      actor: 'local',
      created_at: '2026-11-06T10:00:00Z',
    })
    vi.mocked(generateCommitMessage).mockResolvedValue({
      repository_id: 1,
      message: 'feat: generated message',
      source: 'llm',
      provider: 'lmstudio',
      model: 'qwen2.5-coder-7b-instruct',
      truncated: false,
      diff_chars: 42,
      files_changed: 1,
      warnings: [],
      cached: false,
      generated_at: '2026-11-06T10:00:00Z',
    })
    vi.mocked(explainCve).mockResolvedValue({
      explanation: 'Уязвимость позволяет выполнить код.',
      cached: false,
      model: 'qwen2.5-coder-7b-instruct',
      generated_at: '2026-11-06T10:00:00Z',
    })
    vi.mocked(getCiStatus).mockResolvedValue({
      repository_id: 1,
      branch: 'main',
      github: {
        provider: 'github',
        status: 'completed',
        conclusion: 'success',
        url: null,
      },
      gitflic: {
        provider: 'gitflic',
        status: 'not_supported',
        conclusion: null,
        url: null,
      },
      aggregate: 'success',
    })
  })

  it('opens the confirmation modal from a recommendation', async () => {
    const user = userEvent.setup()
    renderDetails()

    const execute = await screen.findByRole('button', { name: 'Выполнить' })
    await user.click(execute)

    expect(screen.getByText('Подтверждение действия')).toBeInTheDocument()
    expect(
      screen.getByText(/Я понимаю, что действие изменит репозиторий/),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Отмена' })).toBeInTheDocument()
  })

  it('renders running Docker containers and published ports', async () => {
    vi.mocked(getDockerStatus).mockResolvedValue({
      repository_id: 1,
      status: 'running',
      containers: [
        {
          id: 'abc123',
          name: 'web-1',
          image: 'nginx:latest',
          state: 'running',
          status: 'running (healthy)',
          health: 'healthy',
          ports: [
            {
              host_ip: '0.0.0.0',
              host_port: 8080,
              container_port: 80,
              protocol: 'tcp',
            },
          ],
          compose_project: 'app',
          compose_service: 'web',
          match: 'mount_source',
        },
      ],
      error: null,
      checked_at: '2026-11-05T10:00:00Z',
    })

    renderDetails()

    expect(await screen.findByText('Running')).toBeInTheDocument()
    expect(screen.getByText('web-1')).toBeInTheDocument()
    expect(screen.getByText(/8080->80\/tcp/)).toBeInTheDocument()
  })

  it('shows Docker unavailable error without breaking details', async () => {
    renderDetails()

    expect(await screen.findByText('Docker not available')).toBeInTheDocument()
    expect(screen.getByText('Docker daemon not running')).toBeInTheDocument()
    expect(screen.getByText('Статус')).toBeInTheDocument()
  })

  it('shows the no-manifest dependency state', async () => {
    renderDetails()

    expect(await screen.findByText('requirements.txt не найден.')).toBeInTheDocument()
    expect(screen.getByText('Нет манифеста')).toBeInTheDocument()
  })

  it('switches to Node dependencies when package.json is the only manifest', async () => {
    vi.mocked(getDependencies).mockResolvedValue({
      repository_id: 1,
      checked_at: '2026-11-05T10:00:00Z',
      ecosystems: [
        dependenciesNoManifest.ecosystems[0],
        {
          ecosystem: 'node',
          manifest: 'package.json',
          status: 'ok',
          source: 'registry',
          total: 1,
          outdated: 1,
          up_to_date: 0,
          unknown: 0,
          ignored: 0,
          packages: [
            {
              name: 'react',
              declared: '^19.0.0',
              current: '19.0.0',
              latest: '19.2.0',
              status: 'outdated',
              kind: 'range',
              severity: 'minor',
              manifest_line: null,
              manifest_section: 'dependencies',
            },
          ],
          error: null,
        },
      ],
      summary: { total: 1, outdated: 1, up_to_date: 0, unknown: 0, ignored: 0 },
    })

    renderDetails()

    expect(await screen.findByRole('button', { name: 'Node' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(screen.getByText('react')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'react' })).toHaveAttribute(
      'href',
      'https://www.npmjs.com/package/react',
    )
    expect(screen.getByText('1 устарели')).toBeInTheDocument()
  })

  it('switches to .NET dependencies and shows CPM badge', async () => {
    vi.mocked(getDependencies).mockResolvedValue({
      repository_id: 1,
      checked_at: '2026-11-11T10:00:00Z',
      ecosystems: [
        dependenciesNoManifest.ecosystems[0],
        {
          ecosystem: 'node',
          manifest: 'package.json',
          status: 'no_manifest',
          source: 'none',
          total: 0,
          outdated: 0,
          up_to_date: 0,
          unknown: 0,
          ignored: 0,
          packages: [],
          error: null,
        },
        {
          ecosystem: 'dotnet',
          manifest: 'Demo.csproj',
          manifests: ['Demo.csproj', 'Directory.Packages.props'],
          status: 'ok',
          source: 'registry',
          total: 1,
          outdated: 1,
          up_to_date: 0,
          unknown: 0,
          ignored: 0,
          packages: [
            {
              name: 'Newtonsoft.Json',
              declared: '13.0.1',
              current: '13.0.1',
              latest: '13.0.3',
              status: 'outdated',
              kind: 'exact',
              severity: 'patch',
              manifest_line: 4,
              manifest_section: 'PackageReference',
              manifest_path: 'Demo.csproj',
              is_dev: false,
            },
          ],
          error: null,
        },
      ],
      summary: { total: 1, outdated: 1, up_to_date: 0, unknown: 0, ignored: 0 },
    })

    renderDetails()

    expect(
      await screen.findByRole('button', { name: 'C# / .NET' }),
    ).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('link', { name: 'Newtonsoft.Json' })).toHaveAttribute(
      'href',
      'https://www.nuget.org/packages/Newtonsoft.Json',
    )
    expect(screen.getByTestId('central-packages-badge')).toHaveTextContent(
      'Central Package Management',
    )
  })

  it('renders Python dependency counters and outdated packages', async () => {
    vi.mocked(getDependencies).mockResolvedValue({
      repository_id: 1,
      checked_at: '2026-11-05T10:00:00Z',
      ecosystems: [
        {
          ecosystem: 'python',
          manifest: 'requirements.txt',
          status: 'ok',
          source: 'registry',
          total: 2,
          outdated: 1,
          up_to_date: 1,
          unknown: 0,
          ignored: 0,
          packages: [
            {
              name: 'fastapi',
              declared: 'fastapi==0.115.6',
              current: '0.115.6',
              latest: '0.115.6',
              status: 'current',
              kind: 'exact',
              severity: null,
              manifest_line: 1,
              manifest_section: null,
            },
            {
              name: 'requests',
              declared: 'requests>=2.31',
              current: '2.31',
              latest: '2.32.0',
              status: 'outdated',
              kind: 'range',
              severity: 'minor',
              manifest_line: 2,
              manifest_section: null,
            },
          ],
          error: null,
        },
      ],
      summary: { total: 2, outdated: 1, up_to_date: 1, unknown: 0, ignored: 0 },
    })

    renderDetails()

    expect(await screen.findByTestId('dependencies-block')).toBeInTheDocument()
    expect(await screen.findByText('1 устарели')).toBeInTheDocument()
    expect(screen.getByText('requests')).toBeInTheDocument()
    expect(screen.getByText(/2.32.0/)).toBeInTheDocument()
    expect(screen.getByText('minor')).toBeInTheDocument()
  })

  it('renders CVE details in the security block', async () => {
    vi.mocked(getSecurity).mockResolvedValue({
      ...cleanSecurity,
      summary: {
        ...cleanSecurity.summary,
        vulnerable: 1,
        high: 1,
      },
      ecosystems: [
        {
          ...cleanSecurity.ecosystems[0],
          vulnerabilities: [
            {
              package: 'requests',
              version: '2.19.0',
              version_source: 'exact',
              osv_id: 'GHSA-9wx4-h78v-vm56',
              cve_ids: ['CVE-2018-18074'],
              severity: 'high',
              cvss_score: 7.5,
              summary: 'Credentials could be sent to a different host',
              fixed_version: '2.20.0',
              references: [],
            },
          ],
        },
        cleanSecurity.ecosystems[1],
      ],
    })

    renderDetails()

    expect(await screen.findByTestId('security-block')).toBeInTheDocument()
    expect(await screen.findByText('1 high/critical')).toBeInTheDocument()
    expect(screen.getByText('requests')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'CVE-2018-18074' })).toHaveAttribute(
      'href',
      'https://osv.dev/vulnerability/CVE-2018-18074',
    )
    expect(screen.getByText(/исправлено в 2.20.0/)).toBeInTheDocument()
  })

  it('shows a red alert for masked secrets', async () => {
    vi.mocked(getSecurity).mockResolvedValue({
      ...cleanSecurity,
      summary: { ...cleanSecurity.summary, secrets_found: 1 },
      secrets: {
        status: 'ok',
        files_scanned: 4,
        truncated: false,
        findings: [
          {
            file: 'backend/.env',
            line: 3,
            type: 'github_token',
            severity: 'high',
            confidence: 'high',
            preview: 'ghp_****6789',
          },
        ],
        error: null,
      },
    })

    renderDetails()

    expect(
      await screen.findByText('Найдены потенциальные секреты (1)'),
    ).toBeInTheDocument()
    expect(screen.getByText('backend/.env:3')).toBeInTheDocument()
    expect(screen.getByText('ghp_****6789')).toBeInTheDocument()
  })

  it('shows a clean security state', async () => {
    renderDetails()

    const clean = await screen.findAllByText('Уязвимостей не найдено')
    expect(clean.length).toBeGreaterThan(0)
  })

  it('renders hotspots with churn counts', async () => {
    vi.mocked(getInsights).mockResolvedValue({
      ...cleanInsights,
      hotspots: [
        { file: 'backend/app/services/status_service.py', count: 7 },
        { file: 'frontend/src/App.tsx', count: 3 },
      ],
    })

    renderDetails()

    const block = await screen.findByTestId('hotspots-block')
    expect(
      within(block).getByText('backend/app/services/status_service.py'),
    ).toBeInTheDocument()
    expect(within(block).getByText('7')).toBeInTheDocument()
    expect(within(block).getByText('3')).toBeInTheDocument()
  })

  it('renders the activity sparkline for active repositories', async () => {
    vi.mocked(getInsights).mockResolvedValue({
      ...cleanInsights,
      commit_frequency: cleanInsights.commit_frequency.map((point, index) =>
        index === cleanInsights.commit_frequency.length - 1
          ? { ...point, count: 5 }
          : point,
      ),
      summary: { commits: 5, per_day: 0.17, per_week: 1.17 },
    })

    renderDetails()

    expect(await screen.findByTestId('insights-sparkline')).toBeInTheDocument()
    expect(screen.getByText('коммитов: 5')).toBeInTheDocument()
  })

  it('shows no activity when there are no commits', async () => {
    renderDetails()

    expect(await screen.findByText('Нет активности.')).toBeInTheDocument()
  })

  it('generates a commit message for dirty repositories when LLM is enabled', async () => {
    vi.mocked(getSettings).mockResolvedValue({
      ...appSettings,
      llm_enabled: true,
    })
    const user = userEvent.setup()
    renderDetails()

    const generate = await screen.findByRole('button', {
      name: 'Сгенерировать коммит',
    })
    await user.click(generate)

    expect(
      await screen.findByDisplayValue('feat: generated message'),
    ).toBeInTheDocument()
    expect(generateCommitMessage).toHaveBeenCalledWith(1)
  })

  it('commits the edited message after explicit confirmation', async () => {
    vi.mocked(getSettings).mockResolvedValue({
      ...appSettings,
      llm_enabled: true,
    })
    vi.mocked(runAction).mockResolvedValue({
      id: 1,
      repository_id: 1,
      action: 'commit',
      command: 'git commit -m "feat: generated message"',
      status: 'success',
      exit_code: 0,
      output: '[main abc123] feat: generated message',
      error: null,
      duration_ms: 12,
      actor: 'local',
      created_at: '2026-11-06T10:00:00Z',
    })
    const user = userEvent.setup()
    renderDetails()

    await user.click(
      await screen.findByRole('button', { name: 'Сгенерировать коммит' }),
    )
    await screen.findByDisplayValue('feat: generated message')
    await user.click(
      screen.getByRole('checkbox', {
        name: /Я понимаю, что действие создаст коммит/,
      }),
    )
    await user.click(screen.getByRole('button', { name: 'Выполнить коммит' }))

    expect(runAction).toHaveBeenCalledWith(1, 'commit', 'feat: generated message')
  })

  it('explains a CVE through the LLM', async () => {
    vi.mocked(getSettings).mockResolvedValue({
      ...appSettings,
      llm_enabled: true,
    })
    vi.mocked(getSecurity).mockResolvedValue({
      ...cleanSecurity,
      summary: { ...cleanSecurity.summary, vulnerable: 1, high: 1 },
      ecosystems: [
        {
          ...cleanSecurity.ecosystems[0],
          vulnerabilities: [
            {
              package: 'requests',
              version: '2.19.0',
              version_source: 'exact',
              osv_id: 'GHSA-9wx4-h78v-vm56',
              cve_ids: ['CVE-2018-18074'],
              severity: 'high',
              cvss_score: 7.5,
              summary: 'Credentials could be sent to a different host',
              fixed_version: '2.20.0',
              references: [],
            },
          ],
        },
        cleanSecurity.ecosystems[1],
      ],
    })
    const user = userEvent.setup()
    renderDetails()

    await user.click(await screen.findByRole('button', { name: 'Объяснить' }))

    expect(
      await screen.findByText('Уязвимость позволяет выполнить код.'),
    ).toBeInTheDocument()
    expect(explainCve).toHaveBeenCalledWith(
      1,
      'CVE-2018-18074',
      'Credentials could be sent to a different host',
    )
  })

  it('disables dependency updates on a dirty worktree', async () => {
    renderDetails()

    const update = await screen.findByRole('button', {
      name: 'Обновить пакеты',
    })
    expect(update).toBeDisabled()
    expect(update).toHaveAttribute(
      'title',
      'Закоммитьте изменения перед обновлением',
    )
  })

  it('updates dependencies after confirmation', async () => {
    vi.mocked(getStatus).mockResolvedValue({
      ...status,
      state: 'current',
      dirty: { modified: 0, staged: 0, untracked: 0, conflicted: 0 },
    })
    vi.mocked(getDependencies).mockResolvedValue({
      repository_id: 1,
      checked_at: '2026-11-06T10:00:00Z',
      ecosystems: [
        {
          ...dependenciesNoManifest.ecosystems[0],
          status: 'ok',
          total: 0,
        },
      ],
      summary: { total: 0, outdated: 0, up_to_date: 0, unknown: 0, ignored: 0 },
    })
    const user = userEvent.setup()
    renderDetails()

    await user.click(
      await screen.findByRole('button', { name: 'Обновить пакеты' }),
    )
    expect(
      screen.getByText(/Вы собираетесь обновить зависимости/),
    ).toBeInTheDocument()
    const dialog = screen.getByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Обновить' }))

    expect(updateDependencies).toHaveBeenCalledWith(1, 'python')
    expect(await screen.findByText('Зависимости обновлены')).toBeInTheDocument()
  })
})
