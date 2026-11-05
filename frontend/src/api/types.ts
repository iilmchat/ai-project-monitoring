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
  github_full_name: string | null
  gitflic_full_name: string | null
  canonical_provider: string
  mirror_expected: boolean
  mirror_policy: string
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
  mirror_issues: number
  by_state: Record<string, number>
  by_mirror_status: Record<string, number>
}

export interface DashboardRepository extends Repository {
  status: RepositoryStatus | null
  mirror: MirrorStatus | null
  ci?: CISummary | null
}

export interface MirrorProviderStatus {
  full_name: string | null
  branch: string | null
  head_sha: string | null
  head_date: string | null
  private: boolean | null
  checked_at: string | null
}

export interface MirrorStatus {
  repository_id: number
  github: MirrorProviderStatus | null
  gitflic: MirrorProviderStatus | null
  mirror_status: string
  canonical_provider: string
  mirror_expected: boolean
  recommendations: Recommendation[]
  checked_at: string
}

export interface MirrorCandidates {
  github_only: Record<string, unknown>[]
  gitflic_only: Record<string, unknown>[]
  both: Record<string, unknown>[]
  unknown: Record<string, unknown>[]
}

export interface MirrorPolicyUpdate {
  canonical_provider?: 'github' | 'gitflic' | 'both'
  mirror_expected?: boolean
  mirror_policy?: string
  github_full_name?: string
  gitflic_full_name?: string
}

export interface ActionLog {
  id: number
  repository_id: number | null
  action: string
  command: string
  status: 'success' | 'error' | string
  exit_code: number | null
  output: string | null
  error: string | null
  duration_ms: number
  actor: string
  created_at: string
}

export interface ProviderCIStatus {
  provider: string
  status: string
  conclusion: string | null
  url: string | null
}

export interface CIStatus {
  repository_id: number
  branch: string
  github: ProviderCIStatus
  gitflic: ProviderCIStatus
  aggregate: string
}

export interface CISummary {
  github: string
  gitflic: string
  aggregate: string
}

export interface ConflictsResponse {
  repository_id: number
  files: string[]
}

export type HeatmapData = Record<string, number>

export interface AppSettings {
  scan_roots: string
  github_token: string
  gitflic_token: string
  webhook_secret: string
  default_canonical_provider: string
}

export interface SettingsUpdate {
  scan_roots?: string
  github_token?: string
  gitflic_token?: string
  webhook_secret?: string
  default_canonical_provider?: 'github' | 'gitflic'
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

export interface Recommendation {
  action: string
  reason: string
  command: string
  category: string
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
