import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import Documentation from './Documentation.jsx'
import './index.css'

const path = window.location.pathname.replace(/\/$/, '') || '/'
const isDocumentation =
  path === '/documentation' || path === '/documentation.html'

function Root() {
  if (isDocumentation) {
    return <Documentation />
  }
  return <App />
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Root />
  </StrictMode>,
)
