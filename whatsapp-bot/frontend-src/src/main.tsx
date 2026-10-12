import React from 'react'
import ReactDOM from 'react-dom/client'
import { HashRouter } from 'react-router-dom'
import App from './App'
import { AuthGate } from './lib/AuthGate'
import { I18nProvider } from './lib/i18n'
import { BusinessProvider } from './lib/BusinessContext'
import { ErrorBoundary } from './components/ErrorBoundary'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <HashRouter>
        <I18nProvider>
          <AuthGate><BusinessProvider>
            <App />
          </BusinessProvider></AuthGate>
        </I18nProvider>
      </HashRouter>
    </ErrorBoundary>
  </React.StrictMode>,
)
