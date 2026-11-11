import type {
  ActionLog,
  AgentTask,
  AIProviderCreate,
  AIProviderProfile,
  AIProviderUpdate,
  AppSettings,
  AuditLogPage,
  AuthUser,
  AutomationConfig,
  AutomationTool,
  CIStatus,
  CodeIndexJob,
  CodeIndexStatus,
  CodeSearchRequest,
  CodeSearchResponse,
  ChatRequest,
  ChatResponse,
  CommitInfo,
  CommitMessageSuggestion,
  CodeReviewResponse,
  ConflictResolveResponse,
  CveExplanation,
  ReleaseNotesResponse,
  RepositoryTagsResponse,
  CompareResponse,
  ConflictsResponse,
  DashboardAdvice,
  DashboardResponse,
  DependencyReport,
  DockerStatus,
  DuplicatesResponse,
  GlobalDependencyReport,
  GlobalStatsAdvice,
  GlobalStatsReport,
  UnificationAdvice,
  HealthResponse,
  HeatmapData,
  InsightsReport,
  LLMTestResult,
  LoginResponse,
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
  SastExplanation,
  SastReport,
  SettingsStatus,
  SettingsUpdate,
  GigaChatAuthResponse,
  UserCreatePayload,
  UserInviteResponse,
  UserUpdatePayload,
} from './types'

const DEFAULT_API_BASE = '/api/v1'

declare global {
  interface Window {
    __IIRUCHATING_API_BASE__?: string
  }
}

let authToken: string | null = null

export function setAuthToken(token: string | null): void {
  authToken = token
}

export function getAuthToken(): string | null {
  return authToken
}

function apiBase(): string {
  const base = window.__IIRUCHATING_API_BASE__
  if (!base) {
    return DEFAULT_API_BASE
  }
  return `${base.replace(/\/+$/, '')}/api/v1`
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  body?: unknown
  query?: Record<string, string | number | boolean | undefined>
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const url = new URL(`${apiBase()}${path}`, window.location.origin)
  for (const [key, value] of Object.entries(options.query ?? {})) {
    if (value !== undefined) {
      url.searchParams.set(key, String(value))
    }
  }

  const headers: Record<string, string> = {}
  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
  }
  if (authToken) {
    headers.Authorization = `Bearer ${authToken}`
  }

  const response = await fetch(url, {
    method: options.method ?? 'GET',
    credentials: 'include',
    headers: Object.keys(headers).length > 0 ? headers : undefined,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  })

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status} ${response.statusText}`)
  }
  if (response.status === 204) {
    return undefined as T
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
  detectRemote = false,
): Promise<RepositoryListResponse> {
  return request<RepositoryListResponse>('/repositories', {
    query: { skip, limit, detect_remote: detectRemote },
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

export async function reviewCode(
  repositoryId: number,
  language: 'ru' | 'en',
): Promise<CodeReviewResponse> {
  return request<CodeReviewResponse>(
    `/repositories/${repositoryId}/ai/code-review`,
    { method: 'POST', body: { language } },
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

export async function getTags(repositoryId: number): Promise<RepositoryTagsResponse> {
  return request<RepositoryTagsResponse>(`/repositories/${repositoryId}/tags`)
}

export async function resolveConflict(
  repositoryId: number,
  filePath: string,
  language: 'ru' | 'en',
): Promise<ConflictResolveResponse> {
  return request<ConflictResolveResponse>(
    `/repositories/${repositoryId}/ai/resolve-conflict`,
    { method: 'POST', body: { file_path: filePath, language } },
  )
}

export async function generateReleaseNotes(
  repositoryId: number,
  fromTag: string,
  toTag: string,
  language: 'ru' | 'en',
): Promise<ReleaseNotesResponse> {
  return request<ReleaseNotesResponse>(
    `/repositories/${repositoryId}/ai/release-notes`,
    {
      method: 'POST',
      body: { from_tag: fromTag, to_tag: toTag, language },
    },
  )
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
  ecosystem: 'python' | 'node' | 'dotnet' | 'all' = 'all',
  refresh = false,
): Promise<DependencyReport> {
  return request<DependencyReport>(`/repositories/${repositoryId}/dependencies`, {
    query: { ecosystem, refresh },
  })
}

export async function updateDependencies(
  repositoryId: number,
  ecosystem: 'python' | 'node' | 'dotnet',
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

export async function getSast(
  repositoryId: number,
  refresh = false,
): Promise<SastReport> {
  return request<SastReport>(`/repositories/${repositoryId}/sast`, {
    query: { refresh },
  })
}

export async function explainSast(
  repositoryId: number,
  payload: {
    rule_id: string
    message: string
    file: string
    line: number
    snippet: string
  },
): Promise<SastExplanation> {
  return request<SastExplanation>(
    `/repositories/${repositoryId}/ai/sast-explain`,
    { method: 'POST', body: payload },
  )
}

export async function generateAutomation(
  repositoryId: number,
  tool: AutomationTool,
): Promise<AutomationConfig> {
  return request<AutomationConfig>(
    `/repositories/${repositoryId}/automation/generate`,
    { method: 'POST', body: { tool } },
  )
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

export async function getDashboardAdvice(
  language: 'ru' | 'en',
): Promise<DashboardAdvice> {
  return request<DashboardAdvice>('/ai/dashboard-advice', {
    method: 'POST',
    body: { language },
  })
}

export async function getGlobalStats(refresh = false): Promise<GlobalStatsReport> {
  return request<GlobalStatsReport>('/dashboard/global-stats', {
    query: { refresh },
  })
}

export async function getGlobalStatsAdvice(
  language: 'ru' | 'en',
  refresh = false,
): Promise<GlobalStatsAdvice> {
  return request<GlobalStatsAdvice>('/dashboard/global-stats/ai-advice', {
    method: 'POST',
    body: { language },
    query: { refresh },
  })
}

export async function generateAgentTask(
  repositoryId: number,
  language: 'ru' | 'en',
): Promise<AgentTask> {
  return request<AgentTask>(`/repositories/${repositoryId}/ai/agent-task`, {
    method: 'POST',
    body: { language },
  })
}

export async function getAIProviders(): Promise<AIProviderProfile[]> {
  return request<AIProviderProfile[]>('/settings/ai-providers')
}

export interface GigaChatAuthPayload {
  client_id: string
  client_secret: string
  scope: string
  model_name: string
  profile_name: string
  base_url?: string
  activate?: boolean
}

export async function authorizeGigaChat(
  payload: GigaChatAuthPayload,
): Promise<GigaChatAuthResponse> {
  return request<GigaChatAuthResponse>('/settings/ai-providers/gigachat/auth', {
    method: 'POST',
    body: payload,
  })
}

export async function refreshGigaChatToken(
  profileId: number,
): Promise<GigaChatAuthResponse> {
  return request<GigaChatAuthResponse>(
    `/settings/ai-providers/${profileId}/gigachat/refresh`,
    { method: 'POST' },
  )
}

export async function createAIProvider(
  payload: AIProviderCreate,
): Promise<AIProviderProfile> {
  return request<AIProviderProfile>('/settings/ai-providers', {
    method: 'POST',
    body: payload,
  })
}

export async function updateAIProvider(
  profileId: number,
  payload: AIProviderUpdate,
): Promise<AIProviderProfile> {
  return request<AIProviderProfile>(`/settings/ai-providers/${profileId}`, {
    method: 'PATCH',
    body: payload,
  })
}

export async function deleteAIProvider(profileId: number): Promise<void> {
  await request<void>(`/settings/ai-providers/${profileId}`, {
    method: 'DELETE',
  })
}

export async function activateAIProvider(
  profileId: number,
): Promise<AIProviderProfile> {
  return request<AIProviderProfile>(
    `/settings/ai-providers/${profileId}/activate`,
    { method: 'POST' },
  )
}

export async function testLlm(): Promise<LLMTestResult> {
  return request<LLMTestResult>('/settings/llm/test', { method: 'POST' })
}

export async function getDuplicates(): Promise<DuplicatesResponse> {
  return request<DuplicatesResponse>('/dashboard/duplicates')
}

export async function searchCode(
  payload: CodeSearchRequest,
): Promise<CodeSearchResponse> {
  return request<CodeSearchResponse>('/search/code', {
    method: 'POST',
    body: payload,
  })
}

export async function chatWithCode(payload: ChatRequest): Promise<ChatResponse> {
  return request<ChatResponse>('/search/chat', {
    method: 'POST',
    body: payload,
  })
}

export async function indexCode(
  payload: { repository_ids?: number[]; force?: boolean } = {},
): Promise<CodeIndexJob> {
  return request<CodeIndexJob>('/search/code/index', {
    method: 'POST',
    body: payload,
  })
}

export async function getCodeSearchStatus(): Promise<CodeIndexStatus> {
  return request<CodeIndexStatus>('/search/code/status')
}

export async function login(
  username: string,
  password: string,
): Promise<LoginResponse> {
  return request<LoginResponse>('/auth/login', {
    method: 'POST',
    body: { username, password },
  })
}

export async function getCurrentUser(): Promise<AuthUser> {
  return request<AuthUser>('/auth/me')
}

export async function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health')
}

export async function resetDatabase(): Promise<{ status: string }> {
  return request<{ status: string }>('/auth/reset-db', {
    method: 'POST',
    body: { confirm: true },
  })
}

export async function logout(): Promise<void> {
  await request<void>('/auth/logout', { method: 'POST' })
}

export async function getUsers(): Promise<AuthUser[]> {
  return request<AuthUser[]>('/users')
}

export async function inviteUser(
  payload: UserCreatePayload,
): Promise<UserInviteResponse> {
  return request<UserInviteResponse>('/users', {
    method: 'POST',
    body: payload,
  })
}

export async function updateUser(
  userId: number,
  payload: UserUpdatePayload,
): Promise<AuthUser> {
  return request<AuthUser>(`/users/${userId}`, {
    method: 'PATCH',
    body: payload,
  })
}

export async function changePassword(
  oldPassword: string,
  newPassword: string,
): Promise<{ status: string }> {
  return request<{ status: string }>('/users/me/password', {
    method: 'PATCH',
    body: { old_password: oldPassword, new_password: newPassword },
  })
}

export async function resetUserPassword(
  userId: number,
  newPassword: string,
): Promise<{ status: string }> {
  return request<{ status: string }>(`/users/${userId}/reset-password`, {
    method: 'POST',
    body: { new_password: newPassword },
  })
}

export async function getAuditLog(
  limit = 50,
  offset = 0,
): Promise<AuditLogPage> {
  return request<AuditLogPage>('/audit', {
    query: { limit, offset },
  })
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

export async function getSettingsStatus(): Promise<SettingsStatus> {
  return request<SettingsStatus>('/settings/status')
}

export async function updateSettings(payload: SettingsUpdate): Promise<AppSettings> {
  return request<AppSettings>('/settings', { method: 'PATCH', body: payload })
}
