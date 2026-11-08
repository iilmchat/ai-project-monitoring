import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import App from './App'
import './index.css'
import { LanguageProvider } from './i18n'
import { ThemeProvider } from './theme/ThemeContext'

const rootElement = document.getElementById('root')
if (rootElement === null) {
  throw new Error('Root element #root not found')
}
const container: HTMLElement = rootElement

function renderApp(): void {
  createRoot(container).render(
    <StrictMode>
      <ThemeProvider>
        <LanguageProvider>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </LanguageProvider>
      </ThemeProvider>
    </StrictMode>,
  )
}

async function bootstrap(): Promise<void> {
  if ('__TAURI_INTERNALS__' in window) {
    try {
      const { startDesktop } = await import('./desktop/bootstrap')
      if (!(await startDesktop(container))) {
        return
      }
    } catch {
      container.textContent = 'Could not start the local backend.'
      return
    }
  }
  renderApp()
}

void bootstrap()
