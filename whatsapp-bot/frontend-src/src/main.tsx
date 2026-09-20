import React from 'react'
import ReactDOM from 'react-dom/client'
import { HashRouter } from 'react-router-dom'
import App from './App'
import { I18nProvider } from './lib/i18n'
import { BusinessProvider } from './lib/BusinessContext'
import { AuthGate } from './lib/AuthGate'
import Login from './pages/Login'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <I18nProvider>
      <AuthGate loginScreen={(onSuccess) => <Login onSuccess={onSuccess} />}>
        <BusinessProvider>
          <HashRouter>
            <App />
          </HashRouter>
        </BusinessProvider>
      </AuthGate>
    </I18nProvider>
  </React.StrictMode>,
)
