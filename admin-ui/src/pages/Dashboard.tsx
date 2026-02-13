import { useEffect, useState } from 'react'
import { api, type Stats, type SearchLog } from '@/lib/api'
import { Search, Key, ShieldBan, Activity } from 'lucide-react'

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [logs, setLogs] = useState<SearchLog[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    api.getStats().then(setStats).catch((e) => setError(e.message))
    api.getSearchLogs({ page_size: '5' }).then((r) => setLogs(r.items)).catch(() => {})
  }, [])

  if (error) return <div className="p-4 text-red-500">Error: {error}</div>
  if (!stats) return <div className="p-4">Loading...</div>

  const cards = [
    { label: 'Total Searches', value: stats.total_searches, icon: Search, color: 'text-blue-600' },
    { label: 'Today', value: stats.searches_today, icon: Activity, color: 'text-green-600' },
    { label: 'Active Keys', value: stats.active_keys, icon: Key, color: 'text-purple-600' },
    { label: 'Banned IPs', value: stats.banned_ips, icon: ShieldBan, color: 'text-red-600' },
  ]

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {cards.map((c) => (
          <div key={c.label} className="rounded-lg border bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-500">{c.label}</span>
              <c.icon className={`h-5 w-5 ${c.color}`} />
            </div>
            <p className="mt-2 text-3xl font-bold">{c.value}</p>
          </div>
        ))}
      </div>

      <div className="rounded-lg border bg-white p-4 shadow-sm">
        <h2 className="text-lg font-semibold mb-3">Recent Searches</h2>
        {logs.length === 0 ? (
          <p className="text-gray-400 text-sm">No searches yet</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-gray-500">
                <th className="pb-2">Query</th>
                <th className="pb-2">Engine</th>
                <th className="pb-2">IP</th>
                <th className="pb-2">Time</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((l) => (
                <tr key={l.id} className="border-b last:border-0">
                  <td className="py-2 font-medium">{l.query}</td>
                  <td className="py-2">{l.engine || '-'}</td>
                  <td className="py-2 font-mono text-xs">{l.ip_address}</td>
                  <td className="py-2 text-gray-400">{new Date(l.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
