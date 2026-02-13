import { useState } from 'react'
import { BrowserRouter, Routes, Route, NavLink, Navigate } from 'react-router-dom'
import Dashboard from '@/pages/Dashboard'
import SearchHistory from '@/pages/SearchHistory'
import IPMonitor from '@/pages/IPMonitor'
import APIKeys from '@/pages/APIKeys'
import Login from '@/pages/Login'
import { LayoutDashboard, Search, ShieldBan, Key, LogOut } from 'lucide-react'

function Layout({ children, onLogout }: { children: React.ReactNode; onLogout: () => void }) {
  const links = [
    { to: '/admin/', label: 'Dashboard', icon: LayoutDashboard },
    { to: '/admin/search', label: 'Search History', icon: Search },
    { to: '/admin/ips', label: 'IP Monitor', icon: ShieldBan },
    { to: '/admin/keys', label: 'API Keys', icon: Key },
  ]

  return (
    <div className="flex min-h-screen">
      <aside className="w-56 border-r bg-gray-50 p-4 flex flex-col">
        <h2 className="text-lg font-bold mb-6 px-2">WSM Admin</h2>
        <nav className="space-y-1 flex-1">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.to === '/admin/'}
              className={({ isActive }) =>
                `flex items-center gap-2 rounded px-3 py-2 text-sm ${isActive ? 'bg-blue-100 text-blue-700 font-medium' : 'text-gray-600 hover:bg-gray-100'}`
              }
            >
              <l.icon className="h-4 w-4" />
              {l.label}
            </NavLink>
          ))}
        </nav>
        <button onClick={onLogout} className="flex items-center gap-2 rounded px-3 py-2 text-sm text-gray-500 hover:bg-gray-100 mt-auto">
          <LogOut className="h-4 w-4" /> Logout
        </button>
      </aside>
      <main className="flex-1 p-6 bg-gray-50/50">{children}</main>
    </div>
  )
}

export default function App() {
  const [authed, setAuthed] = useState(() => !!localStorage.getItem('admin_token'))

  if (!authed) return <Login onLogin={() => setAuthed(true)} />

  const handleLogout = () => {
    localStorage.removeItem('admin_token')
    setAuthed(false)
  }

  return (
    <BrowserRouter>
      <Layout onLogout={handleLogout}>
        <Routes>
          <Route path="/admin/" element={<Dashboard />} />
          <Route path="/admin/search" element={<SearchHistory />} />
          <Route path="/admin/ips" element={<IPMonitor />} />
          <Route path="/admin/keys" element={<APIKeys />} />
          <Route path="*" element={<Navigate to="/admin/" replace />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}
