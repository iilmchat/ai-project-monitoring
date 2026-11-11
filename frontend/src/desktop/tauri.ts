/**
 * Tauri-only integrations.
 *
 * Plugin modules are imported dynamically so a plain browser build never
 * evaluates them and Vite keeps them out of the entry chunk (S50-002/003).
 */

export function isTauri(): boolean {
  return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window
}

/** Native directory picker. Returns null outside Tauri or when cancelled. */
export async function pickDirectory(): Promise<string | null> {
  if (!isTauri()) {
    return null
  }
  const { open } = await import('@tauri-apps/plugin-dialog')
  const selected = await open({ directory: true, multiple: false })
  return typeof selected === 'string' ? selected : null
}

/** Reveal the application log directory in the OS file manager. */
export interface LogsFolderResult {
  opened: boolean
  path: string
}

export async function openLogsFolder(): Promise<LogsFolderResult> {
  if (!isTauri()) {
    throw new Error('tauri_unavailable')
  }
  const { invoke } = await import('@tauri-apps/api/core')
  const result = await invoke<LogsFolderResult>('open_logs_folder')
  if (!result.path) {
    throw new Error('logs_dir_empty')
  }
  if (!result.opened) {
    await navigator.clipboard.writeText(result.path)
  }
  return result
}
