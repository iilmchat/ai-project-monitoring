import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { check } from '@tauri-apps/plugin-updater'
import { relaunch } from '@tauri-apps/plugin-process'

import { checkForUpdates, installUpdate, relaunchApp } from './updater'

vi.mock('@tauri-apps/plugin-updater', () => ({ check: vi.fn() }))
vi.mock('@tauri-apps/plugin-process', () => ({ relaunch: vi.fn() }))

function setTauri(value: boolean) {
  const target = window as unknown as Record<string, unknown>
  if (value) {
    target.__TAURI_INTERNALS__ = {}
  } else {
    delete target.__TAURI_INTERNALS__
  }
}

describe('updater helpers', () => {
  beforeEach(() => {
    setTauri(true)
    vi.clearAllMocks()
  })

  afterEach(() => {
    setTauri(false)
  })

  it('returns null when the endpoint has no newer release', async () => {
    vi.mocked(check).mockResolvedValue(null)

    await expect(checkForUpdates()).resolves.toBeNull()
  })

  it('returns the announced update', async () => {
    const update = { version: '1.1.0' }
    vi.mocked(check).mockResolvedValue(update as never)

    await expect(checkForUpdates()).resolves.toBe(update)
  })

  it('reports download progress from 0 to 100', async () => {
    const progress: number[] = []
    const update = {
      downloadAndInstall: vi.fn(
        async (onEvent: (event: unknown) => void) => {
          onEvent({ event: 'Started', data: { contentLength: 100 } })
          onEvent({ event: 'Progress', data: { chunkLength: 50 } })
          onEvent({ event: 'Finished' })
        },
      ),
    }

    await installUpdate(update as never, (percent) => progress.push(percent))

    expect(progress).toEqual([0, 50, 100])
  })

  it('relaunches the application after installation', async () => {
    await relaunchApp()

    expect(relaunch).toHaveBeenCalledTimes(1)
  })
})
