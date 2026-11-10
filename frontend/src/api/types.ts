export type RepoState =
  | 'current'
  | 'behind'
  | 'ahead'
  | 'diverged'
  | 'dirty'
  | 'no_upstream'
  | 'detached'
  | 'error'

export interface ReadmeMetadata {
  repository_id: number
  path: string
  name: string
  version: string | null
  content: string
}

export interface RepositoryDoc {
  repository_id: number
  path: string
  content: string
}

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
  manifest_path?: string | null
  is_dev?: boolean
}

export interface DependencyEcosystemReport {
  ecosystem: 'python' | 'node' | 'dotnet'
  manifest: string | null
  manifests?: string[]
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
    | 'unresolved_version'
    | 'unsupported_kind'
    | 'registry_missing'
    | 'osv_unavailable'
}

export interface SecurityEcosystemReport {
  ecosystem: 'python' | 'node' | 'dotnet'
  manifest: string
  manifests?: string[]
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

export type SastSeverity = 'critical' | 'high' | 'medium' | 'low' | 'unknown'
export type SastStatus = 'ok' | 'partial' | 'unavailable'

export interface SastFinding {
  tool: string
  rule_id: string
  severity: SastSeverity
  confidence: string | null
  category: string | null
  cwe: string | null
  file: string
  line: number
  column: number | null
  message: string
  snippet: string | null
  fingerprint: string
}

export interface SastToolReport {
  name: string
  status: 'ok' | 'unavailable' | 'error'
  version: string | null
  duration_ms: number
  error: string | null
}

export interface SastSummary {
  total: number
  critical: number
  high: number
  medium: number
  low: number
  unknown: number
}

export interface SastReport {
  repository_id: number
  checked_at: string
  status: SastStatus
  tools: SastToolReport[]
  summary: SastSummary
  findings: SastFinding[]
  truncated: boolean
  error: string | null
  cached: boolean
}

export interface SastExplanation {
  explanation: string
  cached: boolean
  model: string | null
  generated_at: string
}

export type AutomationTool = 'dependabot' | 'renovate'

export interface AutomationConfig {
  tool: AutomationTool
  path: string
  content: string
  content_hash: string
  ecosystems: string[]
  warnings: string[]
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

export interface SettingsStatus {
  is_configured: boolean
}

export interface AppSettings {
  scan_roots: string
  github_token: string
  gitflic_token: string
  webhook_secret: string
  default_canonical_provider: string
  llm_enabled: boolean
  llm_base_url: string
  llm_model: string
  llm_api_key: string
  llm_timeout_seconds: number
  llm_max_diff_chars: number
  llm_allow_remote: boolean
  telegram_bot_token: string
  telegram_chat_id: string
  notifications_enabled: boolean
  fetch_timeout: number
  status_ttl_seconds: number
  mirror_poll_interval_seconds: number
}

export interface SettingsUpdate {
  scan_roots?: string
  github_token?: string
  gitflic_token?: string
  webhook_secret?: string
  default_canonical_provider?: 'github' | 'gitflic'
  llm_enabled?: boolean
  llm_base_url?: string
  llm_model?: string
  llm_api_key?: string
  llm_timeout_seconds?: number
  llm_max_diff_chars?: number
  llm_allow_remote?: boolean
  telegram_bot_token?: string
  telegram_chat_id?: string
  notifications_enabled?: boolean
  fetch_timeout?: number
  status_ttl_seconds?: number
  mirror_poll_interval_seconds?: number
}

export interface CommitMessageSuggestion {
  repository_id: number
  message: string
  source: 'llm'
  provider: string
  model: string
  truncated: boolean
  diff_chars: number
  files_changed: number
  warnings: string[]
  cached: boolean
  generated_at: string
}

export interface CodeReviewResponse {
  repository_id: number
  review: string
  source: 'llm'
  provider: string
  model: string
  files_reviewed: number
  diff_chars: number
  truncated: boolean
  warnings: string[]
  cached: boolean
  generated_at: string
}

export interface ConflictResolveResponse {
  repository_id: number
  file_path: string
  resolved: string
  blocks: number
  provider: string
  model: string
  truncated: boolean
  warnings: string[]
  cached: boolean
  generated_at: string
}

export interface ReleaseNotesResponse {
  repository_id: number
  from_tag: string
  to_tag: string
  changelog: string
  commits: number
  provider: string
  model: string
  truncated: boolean
  warnings: string[]
  cached: boolean
  generated_at: string
}

export interface RepositoryTagsResponse {
  repository_id: number
  tags: string[]
}

export interface CveExplanation {
  explanation: string
  cached: boolean
  model: string | null
  generated_at: string
}

export interface VersionDistribution {
  version: string
  projects: string[]
}

export interface GlobalDependencyPackage {
  name: string
  latest_version: string | null
  distribution: VersionDistribution[]
  versions_count: number
  projects_count: number
  unification_needed: boolean
}

export interface GlobalDependencySummary {
  repositories: number
  packages: number
  unification_candidates: number
}

export interface GlobalDependencyReport {
  checked_at: string
  ecosystems: {
    python: GlobalDependencyPackage[]
    node: GlobalDependencyPackage[]
  }
  summary: GlobalDependencySummary
  error: string | null
}

export interface AIProviderProfile {
  id: number
  name: string
  base_url: string
  api_key: string
  model_name: string
  is_active: boolean
  created_at: string
  provider_type: 'openai_compatible' | 'gigachat'
  auth_type: 'api_key' | 'oauth'
  client_id: string
  has_client_secret: boolean
  oauth_scope: string | null
  oauth_expires_at: string | null
}

export interface AIProviderCreate {
  name: string
  base_url: string
  model_name: string
  api_key?: string
  provider_type?: 'openai_compatible' | 'gigachat'
  auth_type?: 'api_key' | 'oauth'
  client_id?: string
  client_secret?: string
  oauth_scope?: string
}

export interface AIProviderUpdate {
  name?: string
  base_url?: string
  model_name?: string
  api_key?: string
  provider_type?: 'openai_compatible' | 'gigachat'
  auth_type?: 'api_key' | 'oauth'
  client_id?: string
  client_secret?: string
  oauth_scope?: string
}

export interface GigaChatAuthResponse {
  profile_id: number
  status: 'ok'
  expires_at: string
  model_name: string
}

export interface DashboardAdvice {
  advice: string
  cached: boolean
  model: string | null
  generated_at: string
  stats: Record<string, number>
}

export interface AgentTask {
  task: string
  model: string | null
  generated_at: string
}

export interface CodeSearchResult {
  repository_id: number
  repository_name: string
  path: string
  start_line: number
  end_line: number
  language: string
  snippet: string
  score: number
  url: string | null
}

export interface CodeSearchResponse {
  query: string
  model: string
  took_ms: number
  indexed_repositories: number
  stale: boolean
  results: CodeSearchResult[]
}

export interface CodeSearchRequest {
  query: string
  repository_ids?: number[]
  limit?: number
  min_score?: number
  language?: string
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface ChatRequest {
  query: string
  history: ChatMessage[]
  repository_ids?: number[]
  limit?: number
  min_score?: number
}

export interface ChatResponse {
  answer: string
  sources: string[]
  citations: CodeSearchResult[]
  model: string
  embedding_model: string
  took_ms: number
}

export interface CodeIndexStatus {
  indexed_repositories: number
  indexed_chunks: number
  last_indexed_at: string | null
  running: boolean
  errors: string[]
}

export interface CodeIndexJob {
  status: 'started' | 'running' | 'completed' | 'failed'
  message: string | null
  started_at: string
}

export interface LLMTestResult {
  status: 'ok' | 'error'
  latency_ms: number
  error: string | null
}

export type UserRole = 'admin' | 'auditor'

export interface AuthUser {
  id: number
  username: string
  role: UserRole
  is_active: boolean
  created_at?: string | null
  last_login_at?: string | null
}

export interface UserInviteResponse {
  user: AuthUser
  temporary_password: string | null
}

export interface UserCreatePayload {
  username: string
  role: UserRole
  password?: string
}

export interface UserUpdatePayload {
  role?: UserRole
  is_active?: boolean
  password?: string
}

export interface AuditActor {
  id: number | null
  username: string | null
}

export interface AuditEntry {
  id: number
  created_at: string
  user: AuditActor
  action: string
  entity_type: string | null
  entity_id: string | null
  details: Record<string, unknown>
}

export interface AuditLogPage {
  items: AuditEntry[]
  total: number
  limit: number
  offset: number
}

export interface LoginResponse {
  access_token: string
  token_type: string
  expires_at: string
  user: AuthUser
}

export interface UnificationAdvice {
  ecosystem: 'python' | 'node'
  package: string
  advice: string
  cached: boolean
  model: string | null
  generated_at: string
}

export interface DuplicateRepository {
  id: number
  path: string
  name: string
}

export interface DuplicateGroup {
  remote_url: string
  repositories: DuplicateRepository[]
}

export interface DuplicatesResponse {
  groups: DuplicateGroup[]
  checked: number
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
