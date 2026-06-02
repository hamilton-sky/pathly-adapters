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

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
