import type {
  CommitInfo,
  CompareResponse,
  DashboardResponse,
  Recommendation,
  Repository,
  RepositoryListResponse,
  RepositoryStatus,
  ScanStarted,
  ScanStatus,
} from './types'

const API_BASE = '/api/v1'

interface RequestOptions {
  method?: 'GET' | 'POST'
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
