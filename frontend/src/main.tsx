import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.tsx'
import './index.css'
import { applyPreferences, loadPreferences } from './services/preferences.ts'
import { AppProvider } from './state/AppContext.tsx'

// Apply saved display settings before the first paint so the page doesn't flash at default size.
applyPreferences(loadPreferences())

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <AppProvider>
        <App />
      </AppProvider>
    </BrowserRouter>
  </StrictMode>,
)
