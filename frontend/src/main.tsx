import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { registerSW } from 'virtual:pwa-register'
import './index.css'
import './App.css'
import App from './App.tsx'
import { initFrontendDiagnostics } from './utils/diagnostics'

registerSW({ immediate: true })

initFrontendDiagnostics()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
