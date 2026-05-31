import React from 'react'
import ReactDOM from 'react-dom/client'
// HashRouter (not BrowserRouter) so deep links like /PACT/#/runs/xyz work on
// GitHub Pages without server-side rewrite support. The real frontend/ keeps
// BrowserRouter.
import { HashRouter } from 'react-router-dom'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <HashRouter>
      <App />
    </HashRouter>
  </React.StrictMode>,
)
