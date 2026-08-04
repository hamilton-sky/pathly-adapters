import '@fontsource/geist/400.css'
import '@fontsource/geist/500.css'
import '@fontsource/geist/600.css'
import '@fontsource/geist-mono/400.css'
import './styles/tokens.css'
import './styles/buttons.css'
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { registerElementResolver } from './lib/elementResolver'

registerElementResolver()

// Tag the OS so the title bar can reserve space for the native window controls:
// macOS draws its traffic-light buttons over the top-LEFT corner (titleBarStyle:'hidden'),
// while Windows/Linux put min/max/close on the top-RIGHT. TopBar.module.css keys its insets
// off this attribute so the logo/home button never hides beneath the traffic lights.
const isMac =
  navigator.userAgent.includes('Macintosh') ||
  navigator.platform.toLowerCase().startsWith('mac')
document.documentElement.dataset.platform = isMac ? 'mac' : 'other'

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
