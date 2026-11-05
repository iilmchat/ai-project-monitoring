export type RepoState =
  | 'current'
  | 'behind'
  | 'ahead'
  | 'diverged'
  | 'dirty'
  | 'no_upstream'
  | 'detached'
  | 'error'

export interface Repository {
  id: number
  path: string
  alias: string | null
  tracked: boolean
  created_at: string
  updated_at: string
}

export interface DirtyCounts {
  modified: number
  staged: number
  untracked: number
  conflicted: number
}

export interface RepositoryStatus {
  repository_id: number
  path: string
  branch: string | null
  head_sha: string | null
  head_subject: string | null
  head_date: string | null
  upstream: string | null
  ahead: number
  behind: number
  state: RepoState | string
  dirty: DirtyCounts
  detached: boolean
  remote_status: 'ok' | 'stale' | 'unavailable' | string
  error: string | null
  checked_at: string
}

export interface DashboardSummary {
  total: number
  clean: number
  needs_attention: number
  untracked: number
  stale: number
  errors: number
}

export interface DashboardRepository extends Repository {
  status: RepositoryStatus | null
}

export interface DashboardResponse {
  summary: DashboardSummary
  repositories: DashboardRepository[]
}

export interface RepositoryListResponse {
  items: Repository[]
  total: number
  skip: number
  limit: number
}

export interface CommitInfo {
  sha: string
  subject: string
  author: string
  date: string
}

export interface CompareResponse {
  ahead: number
  behind: number
  status: 'ahead' | 'behind' | 'diverged' | 'identical' | 'unavailable' | string
  commits: CommitInfo[]
}

export interface ScanStarted {
  scan_id: number
  started_at: string
}

export interface ScanStatus {
  id: number
  status: string
  started_at: string
  finished_at: string | null
  found: number
  added: number
  skipped: number
  errors: string[]
}
