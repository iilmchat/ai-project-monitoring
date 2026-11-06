import type { DashboardRepository, DashboardSummary } from '../api/types'

const ATTENTION_STATES = new Set([
  'dirty',
  'ahead',
  'behind',
  'diverged',
  'no_upstream',
  'detached',
  'error',
])

const MIRROR_ISSUE_STATES = new Set([
  'missing_on_gitflic',
  'missing_on_github',
  'behind_gitflic',
  'behind_github',
  'diverged',
  'history_rewritten',
  'unavailable',
])

function displayName(repository: DashboardRepository): string {
  if (repository.alias) {
    return repository.alias
  }
  const normalized = repository.path.replaceAll('\\', '/')
  return normalized.split('/').filter(Boolean).pop() ?? repository.path
}

function escapeText(value: string): string {
  return value.replace(/([\\`*_[\]<>])/g, '\\$1')
}

function escapeInlineCode(value: string): string {
  return value.replace(/`/g, "'")
}

function isoDate(value: Date): string {
  return value.toISOString().slice(0, 10)
}

export interface MarkdownSummaryInput {
  summary?: DashboardSummary
  repositories: DashboardRepository[]
  generatedAt?: Date
}

/**
 * Build the clipboard summary for the currently visible dashboard slice.
 * Counts come from ``summary`` when available; the problem list always
 * reflects the filtered repositories the user sees.
 */
export function buildDashboardMarkdown({
  summary,
  repositories,
  generatedAt = new Date(),
}: MarkdownSummaryInput): string {
  const attention = repositories.filter((repository) =>
    ATTENTION_STATES.has(repository.status?.state ?? ''),
  )
  const mirrorIssues = repositories.filter((repository) =>
    MIRROR_ISSUE_STATES.has(repository.mirror?.mirror_status ?? ''),
  )

  const total = summary?.total ?? repositories.length
  const needsAttention = summary?.needs_attention ?? attention.length
  const mirrorCount = summary?.mirror_issues ?? mirrorIssues.length

  const lines = [
    `## IIRuchating Summary (${isoDate(generatedAt)})`,
    `- Всего репозиториев: ${total}`,
    `- Требуют внимания: ${needsAttention} (dirty, ahead, behind)`,
    `- Зеркала расходятся: ${mirrorCount}`,
    '',
    '### Проблемные проекты:',
  ]

  if (attention.length === 0) {
    lines.push('_Проблемных проектов нет._')
    return lines.join('\n')
  }

  for (const repository of attention) {
    const name = escapeText(displayName(repository))
    const path = escapeInlineCode(repository.path)
    const state = repository.status?.state ?? 'unknown'
    const ahead = repository.status?.ahead ?? 0
    const behind = repository.status?.behind ?? 0
    const counters =
      ahead > 0 || behind > 0 ? ` (${ahead} ahead, ${behind} behind)` : ''
    const mirror = repository.mirror?.mirror_status
    const mirrorSuffix =
      mirror && MIRROR_ISSUE_STATES.has(mirror) ? ` — [Mirror: ${mirror}]` : ''
    lines.push(
      `- **${name}** (\`${path}\`): ${state}${counters}${mirrorSuffix}`,
    )
  }

  return lines.join('\n')
}
