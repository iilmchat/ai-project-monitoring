/**
 * Tauri auto-update helpers (S51-002).
 *
 * Plugin modules are imported dynamically so a browser build never evaluates
 * them and Vite keeps them out of the entry chunk.
 */

import type { Update } from '@tauri-apps/plugin-updater'

import { isTauri } from './tauri'

export type { Update }

/** Ask the configured endpoint whether a newer release exists. */
export async function checkForUpdates(): Promise<Update | null> {
  if (!isTauri()) {
    throw new Error('tauri_unavailable')
  }
  const { check } = await import('@tauri-apps/plugin-updater')
  return check()
}

/** Download and install an update, reporting progress from 0 to 100. */
export async function installUpdate(
  update: Update,
  onProgress: (percent: number) => void,
): Promise<void> {
  let downloaded = 0
  let total = 0

  await update.downloadAndInstall((event) => {
    if (event.event === 'Started') {
      total = event.data.contentLength ?? 0
      onProgress(0)
      return
    }
    if (event.event === 'Progress') {
      downloaded += event.data.chunkLength
      if (total > 0) {
        onProgress(Math.min(100, Math.round((downloaded / total) * 100)))
      }
      return
    }
    onProgress(100)
  })
}

/** Restart the application after the update has been installed. */
export async function relaunchApp(): Promise<void> {
  const { relaunch } = await import('@tauri-apps/plugin-process')
  await relaunch()
}
