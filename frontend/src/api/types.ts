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

export type DockerStatusValue = 'running' | 'stopped' | 'not_found' | 'unavailable'

export interface DockerPort {
  host_ip: string | null
  host_port: number | null
  container_port: number | null
  protocol: string
}

export interface DockerContainer {
  id: string
  name: string
  image: string
  state: string
  status: string
  health: string | null
  ports: DockerPort[]
  compose_project: string | null
  compose_service: string | null
  match: string
}

export interface DockerStatus {
  repository_id: number
  status: DockerStatusValue
  containers: DockerContainer[]
  error: string | null
  checked_at: string
}

export type DependencyPackageStatus = 'outdated' | 'current' | 'unknown' | 'ignored'
export type DependencyPackageKind = 'exact' | 'range' | 'vcs' | 'path' | 'workspace'
export type DependencySeverity = 'major' | 'minor' | 'patch'

export interface DependencyPackage {
  name: string
  declared: string
  current: string | null
  latest: string | null
  status: DependencyPackageStatus
  kind: DependencyPackageKind
  severity: DependencySeverity | null
  manifest_line: number | null
  manifest_section: string | null
}

export interface DependencyEcosystemReport {
  ecosystem: 'python' | 'node'
  manifest: string | null
  status: 'ok' | 'no_manifest' | 'parse_error' | 'unavailable'
  source: 'registry' | 'cache' | 'mixed' | 'stale_cache' | 'none'
  total: number
  outdated: number
  up_to_date: number
  unknown: number
  ignored: number
  packages: DependencyPackage[]
  error: string | null
}

export interface DependencySummary {
  total: number
  outdated: number
  up_to_date: number
  unknown: number
  ignored: number
}

export interface DependencyReport {
  repository_id: number
  checked_at: string
  ecosystems: DependencyEcosystemReport[]
  summary: DependencySummary
}

export type SecuritySeverity = 'critical' | 'high' | 'medium' | 'low' | 'unknown'
export type SecurityVersionSource = 'exact' | 'lower_bound'
export type SecurityEcosystemStatus =
  | 'ok'
  | 'no_manifest'
  | 'parse_error'
  | 'unavailable'

export interface SecurityVulnerability {
  package: string
  version: string
  version_source: SecurityVersionSource
  osv_id: string
  cve_ids: string[]
  severity: SecuritySeverity
  cvss_score: number | null
  summary: string | null
  fixed_version: string | null
  references: string[]
}

export interface SecurityUnknownPackage {
  name: string
  reason:
    | 'unresolved_range'
    | 'unsupported_kind'
    | 'registry_missing'
    | 'osv_unavailable'
}

export interface SecurityEcosystemReport {
  ecosystem: 'python' | 'node'
  manifest: string
  status: SecurityEcosystemStatus
  total_packages: number
  packages_checked: number
  vulnerabilities: SecurityVulnerability[]
  unknown_packages: SecurityUnknownPackage[]
  error: string | null
}

export interface SecretFinding {
  file: string
  line: number
  type: 'aws_access_key' | 'aws_secret_key' | 'github_token' | 'jwt' | 'private_key'
  severity: 'high' | 'medium'
  confidence: 'high' | 'medium'
  preview: string
}

export interface SecretScanReport {
  status: 'ok' | 'skipped' | 'partial' | 'unavailable'
  files_scanned: number
  truncated: boolean
  findings: SecretFinding[]
  error: string | null
}

export interface SecuritySummary {
  total_packages: number
  packages_checked: number
  vulnerable: number
  critical: number
  high: number
  medium: number
  low: number
  unknown: number
  secrets_found: number
}

export interface SecurityReport {
  repository_id: number
  checked_at: string
  status: 'ok' | 'unavailable'
  summary: SecuritySummary
  ecosystems: SecurityEcosystemReport[]
  secrets: SecretScanReport
  error: string | null
}

export type InsightsStatus =
  | 'ok'
  | 'partial'
  | 'no_branch'
  | 'shallow_clone'
  | 'timeout'
  | 'unavailable'

export interface InsightsWindow {
  days: number
  since: string
  until: string
  branch: string | null
  hotspots_days: number
}

export interface Hotspot {
  file: string
  count: number
}

export interface CommitFrequencyPoint {
  date: string
  count: number
}

export interface InsightsSummary {
  commits: number
  per_day: number
  per_week: number
}

export interface InsightsReport {
  repository_id: number
  checked_at: string
  status: InsightsStatus
  window: InsightsWindow
  hotspots: Hotspot[]
  commit_frequency: CommitFrequencyPoint[]
  summary: InsightsSummary
  error: string | null
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
