import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  getActions,
  getCiStatus,
  getConflicts,
  getDependencies,
  getDockerStatus,
  getLog,
  getMirror,
  getRecommendations,
  getRepositories,
  getStatus,
} from '../api/client'
import type {
  DashboardRepository,
  DependencyReport,
  DockerStatus,
  MirrorStatus,
  RepositoryStatus,
} from '../api/types'
import RepositoryDetails from './RepositoryDetails'

vi.mock('../api/client', () => ({
  getActions: vi.fn(),
  getCiStatus: vi.fn(),
  getConflicts: vi.fn(),
  getDependencies: vi.fn(),
  getDockerStatus: vi.fn(),
  getLog: vi.fn(),
  getMirror: vi.fn(),
  getRecommendations: vi.fn(),
  getRepositories: vi.fn(),
  getStatus: vi.fn(),
  refreshMirror: vi.fn(),
  refreshRepository: vi.fn(),
  runAction: vi.fn(),
  runMirrorAction: vi.fn(),
  updateMirrorPolicy: vi.fn(),
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
}

function renderDetails() {
  return render(
    <MemoryRouter initialEntries={['/repo/1']}>
      <Routes>
        <Route path="/repo/:id" element={<RepositoryDetails />} />
      </Routes>
    </MemoryRouter>,
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
    vi.mocked(getActions).mockResolvedValue([])
    vi.mocked(getConflicts).mockResolvedValue({ repository_id: 1, files: [] })
    vi.mocked(getDockerStatus).mockResolvedValue(dockerUnavailable)
    vi.mocked(getDependencies).mockResolvedValue(dependenciesNoManifest)
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
    })

    renderDetails()

    expect(await screen.findByTestId('dependencies-block')).toBeInTheDocument()
    expect(await screen.findByText('1 устарели')).toBeInTheDocument()
    expect(screen.getByText('requests')).toBeInTheDocument()
    expect(screen.getByText(/2.32.0/)).toBeInTheDocument()
    expect(screen.getByText('minor')).toBeInTheDocument()
  })
})
