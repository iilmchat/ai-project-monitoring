import type {
  ActionLog,
  AppSettings,
  CIStatus,
  CommitInfo,
  CommitMessageSuggestion,
  CveExplanation,
  CompareResponse,
  ConflictsResponse,
  DashboardResponse,
  DependencyReport,
  DockerStatus,
  DuplicatesResponse,
  GlobalDependencyReport,
  UnificationAdvice,
  HeatmapData,
  InsightsReport,
  MirrorCandidates,
  MirrorPolicyUpdate,
  MirrorStatus,
  ReadmeMetadata,
  Recommendation,
  Repository,
  RepositoryDoc,
  RepositoryListResponse,
  RepositoryStatus,
  ScanStarted,
  ScanStatus,
  SecurityReport,
  SettingsUpdate,
} from './types'

const API_BASE = '/api/v1'

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH'
  body?: unknown
  query?: Record<string, string | number | boolean | undefined>
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const url = new URL(`${API_BASE}${path}`, window.location.origin)
  for (const [key, value] of Object.entries(options.query ?? {})) {
    if (value !== undefined) {
      url.searchParams.set(key, String(value))
    }
  }

  const response = await fetch(url, {
    method: options.method ?? 'GET',
    headers: options.body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  })

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status} ${response.statusText}`)
  }
  return (await response.json()) as T
}

export async function getDashboard(trackedOnly = false): Promise<DashboardResponse> {
  return request<DashboardResponse>('/dashboard', {
    query: trackedOnly ? { tracked_only: true } : undefined,
  })
}

export async function scan(roots?: string[]): Promise<ScanStarted> {
  return request<ScanStarted>('/scan', {
    method: 'POST',
    body: roots ? { roots } : {},
  })
}

export async function getScan(scanId: number): Promise<ScanStatus> {
  return request<ScanStatus>(`/scan/${scanId}`)
}

export async function getRepositories(
  skip = 0,
  limit = 500,
): Promise<RepositoryListResponse> {
  return request<RepositoryListResponse>('/repositories', {
    query: { skip, limit },
  })
}

export async function getReadme(repositoryId: number): Promise<ReadmeMetadata> {
  return request<ReadmeMetadata>(`/repositories/${repositoryId}/readme`)
}

export async function getRepositoryDoc(
  repositoryId: number,
  path: string,
): Promise<RepositoryDoc> {
  return request<RepositoryDoc>(`/repositories/${repositoryId}/docs`, {
    query: { path },
  })
}

export async function getStatus(
  repositoryId: number,
  fetchFromRemote = true,
): Promise<RepositoryStatus> {
  return request<RepositoryStatus>(`/repositories/${repositoryId}/status`, {
    query: { fetch: fetchFromRemote },
  })
}

export async function refreshRepository(
  repositoryId: number,
  fetchFromRemote = true,
): Promise<RepositoryStatus> {
  return request<RepositoryStatus>(`/repositories/${repositoryId}/refresh`, {
    method: 'POST',
    body: { fetch: fetchFromRemote },
  })
}

export async function trackRepository(repositoryId: number): Promise<Repository> {
  return request<Repository>(`/repositories/${repositoryId}/track`, { method: 'POST' })
}

export async function untrackRepository(repositoryId: number): Promise<Repository> {
  return request<Repository>(`/repositories/${repositoryId}/untrack`, { method: 'POST' })
}

export async function getCompare(
  repositoryId: number,
  base?: string,
  head?: string,
): Promise<CompareResponse> {
  return request<CompareResponse>(`/repositories/${repositoryId}/compare`, {
    query: { base, head },
  })
}

export async function getLog(repositoryId: number, limit = 20): Promise<CommitInfo[]> {
  return request<CommitInfo[]>(`/repositories/${repositoryId}/log`, {
    query: { limit },
  })
}

export async function getRecommendations(repositoryId: number): Promise<Recommendation[]> {
  return request<Recommendation[]>(`/repositories/${repositoryId}/recommendations`)
}

export async function getMirror(repositoryId: number, refresh = false): Promise<MirrorStatus> {
  return request<MirrorStatus>(`/repositories/${repositoryId}/mirror`, {
    query: { refresh },
  })
}

export async function refreshMirror(repositoryId: number): Promise<MirrorStatus> {
  return request<MirrorStatus>(`/repositories/${repositoryId}/mirror/refresh`, {
    method: 'POST',
  })
}

export async function updateMirrorPolicy(
  repositoryId: number,
  payload: MirrorPolicyUpdate,
): Promise<Repository> {
  return request<Repository>(`/repositories/${repositoryId}/mirror-policy`, {
    method: 'PATCH',
    body: payload,
  })
}

export async function getMirrorCandidates(): Promise<MirrorCandidates> {
  return request<MirrorCandidates>('/mirror/candidates')
}

export async function runAction(
  repositoryId: number,
  action: string,
  message?: string,
): Promise<ActionLog> {
  return request<ActionLog>(`/repositories/${repositoryId}/actions/${action}`, {
    method: 'POST',
    body: message === undefined ? { confirm: true } : { confirm: true, message },
  })
}

export async function generateCommitMessage(
  repositoryId: number,
): Promise<CommitMessageSuggestion> {
  return request<CommitMessageSuggestion>(
    `/repositories/${repositoryId}/ai/commit-message`,
    { method: 'POST' },
  )
}

export async function runMirrorAction(
  repositoryId: number,
  action: string,
): Promise<ActionLog> {
  return request<ActionLog>(`/mirror/actions/${action}`, {
    method: 'POST',
    body: { confirm: true, repository_id: repositoryId },
  })
}

export async function getActions(repositoryId: number, limit = 20): Promise<ActionLog[]> {
  return request<ActionLog[]>(`/repositories/${repositoryId}/actions`, {
    query: { limit },
  })
}

export async function getCiStatus(repositoryId: number): Promise<CIStatus> {
  return request<CIStatus>(`/repositories/${repositoryId}/ci-status`)
}

export async function getConflicts(repositoryId: number): Promise<ConflictsResponse> {
  return request<ConflictsResponse>(`/repositories/${repositoryId}/conflicts`)
}

export async function getDockerStatus(
  repositoryId: number,
  refresh = false,
): Promise<DockerStatus> {
  return request<DockerStatus>(`/repositories/${repositoryId}/docker`, {
    query: { refresh },
  })
}

export async function getDependencies(
  repositoryId: number,
  ecosystem: 'python' | 'node' | 'all' = 'all',
  refresh = false,
): Promise<DependencyReport> {
  return request<DependencyReport>(`/repositories/${repositoryId}/dependencies`, {
    query: { ecosystem, refresh },
  })
}

export async function updateDependencies(
  repositoryId: number,
  ecosystem: 'python' | 'node',
): Promise<ActionLog> {
  return request<ActionLog>(
    `/repositories/${repositoryId}/actions/update-dependencies`,
    {
      method: 'POST',
      body: { confirm: true, ecosystem },
    },
  )
}

export async function getSecurity(
  repositoryId: number,
  refresh = false,
  minSeverity: 'critical' | 'high' | 'medium' | 'low' | 'all' = 'high',
): Promise<SecurityReport> {
  return request<SecurityReport>(`/repositories/${repositoryId}/security`, {
    query: { refresh, min_severity: minSeverity },
  })
}

export async function getInsights(
  repositoryId: number,
  days = 30,
  refresh = false,
): Promise<InsightsReport> {
  return request<InsightsReport>(`/repositories/${repositoryId}/insights`, {
    query: { days, refresh },
  })
}

export async function explainCve(
  repositoryId: number,
  cveId: string,
  summary: string,
): Promise<CveExplanation> {
  return request<CveExplanation>(
    `/repositories/${repositoryId}/ai/cve-explain`,
    {
      method: 'POST',
      body: { cve_id: cveId, summary },
    },
  )
}

export async function getGlobalDependencies(
  refresh = false,
): Promise<GlobalDependencyReport> {
  return request<GlobalDependencyReport>('/dashboard/global-dependencies', {
    query: { refresh },
  })
}

export async function getDuplicates(): Promise<DuplicatesResponse> {
  return request<DuplicatesResponse>('/dashboard/duplicates')
}

export async function getUnificationAdvice(
  ecosystem: 'python' | 'node',
  packageName: string,
): Promise<UnificationAdvice> {
  return request<UnificationAdvice>(
    '/dashboard/global-dependencies/ai-advice',
    {
      method: 'POST',
      body: { ecosystem, package: packageName },
    },
  )
}

export async function getHeatmap(days = 365): Promise<HeatmapData> {
  return request<HeatmapData>('/dashboard/heatmap', { query: { days } })
}

export async function exportRepositories(format: 'csv' | 'json'): Promise<Blob> {
  const response = await fetch(`/api/v1/repositories/export?format=${format}`)
  if (!response.ok) {
    throw new Error(`export failed: ${response.status}`)
  }
  return response.blob()
}

export async function bulkFetchAll(
  repoIds?: number[],
  trackedOnly = true,
): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>('/repositories/actions/fetch_all', {
    method: 'POST',
    query: { tracked_only: trackedOnly },
    body: repoIds ? { repo_ids: repoIds } : {},
  })
}

export async function bulkSyncMirrorsAll(
  repoIds?: number[],
  trackedOnly = true,
): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>('/repositories/actions/sync_mirrors_all', {
    method: 'POST',
    query: { tracked_only: trackedOnly },
    body: repoIds ? { repo_ids: repoIds } : {},
  })
}

export async function migrateToGitflic(): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>('/repositories/actions/migrate_to_gitflic', {
    method: 'POST',
  })
}

export async function getSettings(): Promise<AppSettings> {
  return request<AppSettings>('/settings')
}

export async function updateSettings(payload: SettingsUpdate): Promise<AppSettings> {
  return request<AppSettings>('/settings', { method: 'PATCH', body: payload })
}
