import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import App from './App'
import './index.css'
import { LanguageProvider } from './i18n'
import { ThemeProvider } from './theme/ThemeContext'

const container = document.getElementById('root')
if (container === null) {
  throw new Error('Root element #root not found')
}

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
