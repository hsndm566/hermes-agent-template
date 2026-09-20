import { Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import Overview from './pages/Overview'
import BotWhatsApp from './pages/BotWhatsApp'
import Conversations from './pages/Conversations'
import Appointments from './pages/Appointments'
import Customers from './pages/Customers'
import Services from './pages/Services'
import Team from './pages/Team'
import Availability from './pages/Availability'
import AutomationsPage from './pages/Automations'
import SettingsPage from './pages/Settings'

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Overview />} />
        <Route path="conversations" element={<Conversations />} />
        <Route path="appointments" element={<Appointments />} />
        <Route path="customers" element={<Customers />} />
        <Route path="services" element={<Services />} />
        <Route path="team" element={<Team />} />
        <Route path="availability" element={<Availability />} />
        <Route path="whatsapp" element={<BotWhatsApp />} />
        <Route path="automations" element={<AutomationsPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  )
}
