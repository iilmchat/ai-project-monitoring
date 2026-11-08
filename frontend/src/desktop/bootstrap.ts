const HEALTH_TIMEOUT_MS = 120_000

function splash(container: HTMLElement, message: string): void {
  container.innerHTML = `
    <div style="min-height:100vh;display:flex;align-items:center;justify-content:center;background:#0f172a;color:#e2e8f0;font-family:Inter,system-ui,sans-serif">
      <div style="text-align:center">
        <div style="width:44px;height:44px;margin:0 auto 16px;border:3px solid #38bdf8;border-top-color:transparent;border-radius:50%;animation:spin 1s linear infinite"></div>
        <p style="font-size:15px">${message}</p>
      </div>
      <style>@keyframes spin{to{transform:rotate(360deg)}}</style>
    </div>
  `
}

function splashError(container: HTMLElement, message: string): void {
  container.innerHTML = `
    <div style="min-height:100vh;display:flex;align-items:center;justify-content:center;background:#0f172a;color:#e2e8f0;font-family:Inter,system-ui,sans-serif;padding:24px">
      <div style="max-width:480px;text-align:center">
        <h1 style="font-size:20px;margin:0 0 8px">IIRuchating</h1>
        <p style="font-size:14px;color:#fca5a5">${message}</p>
        <button id="retry" style="margin-top:16px;padding:8px 16px;border:0;border-radius:8px;background:#38bdf8;color:#0f172a;font-weight:600;cursor:pointer">Retry</button>
      </div>
    </div>
  `
  document.getElementById('retry')?.addEventListener('click', () => {
    window.location.reload()
  })
}

async function waitForBackend(base: string): Promise<void> {
  const deadline = Date.now() + HEALTH_TIMEOUT_MS
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${base}/api/v1/health`, { cache: 'no-store' })
      if (response.ok) {
        const payload = (await response.json()) as { status?: string }
        if (payload.status === 'ok') {
          return
        }
      }
    } catch {
      // backend is still starting
    }
    await new Promise((resolve) => window.setTimeout(resolve, 500))
  }
  throw new Error('backend_timeout')
}

/** Start the Tauri sidecar connection and wait until the backend is healthy. */
export async function startDesktop(container: HTMLElement): Promise<boolean> {
  splash(container, 'Starting IIRuchating…')
  try {
    const { invoke } = await import('@tauri-apps/api/core')
    const base = await invoke<string>('backend_url')
    if (!base) {
      throw new Error('backend_url_empty')
    }
    window.__IIRUCHATING_API_BASE__ = base
    splash(container, 'Waiting for the backend…')
    await waitForBackend(base)
    return true
  } catch {
    splashError(container, 'Could not start the local backend. Check the application logs.')
    return false
  }
}
