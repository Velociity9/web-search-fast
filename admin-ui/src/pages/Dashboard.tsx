import { useEffect, useState } from 'react'
import { api, type Stats, type SearchLog, type SystemInfo, type Analytics } from '@/lib/api'
import { Search, Key, ShieldBan, Activity, Cpu, HardDrive, Monitor, Globe } from 'lucide-react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
} from 'recharts'

function formatHour(hour: string): string {
  return hour.split(' ')[1] || hour
}

function percentColor(value: number, thresholds = { green: 50, yellow: 80 }): string {
  if (value < thresholds.green) return 'text-green-600'
  if (value < thresholds.yellow) return 'text-yellow-600'
  return 'text-red-600'
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [logs, setLogs] = useState<SearchLog[]>([])
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null)
  const [analytics, setAnalytics] = useState<Analytics | null>(null)
  const [timeRange, setTimeRange] = useState<'24h' | '7d'>('24h')
  const [error, setError] = useState('')

  useEffect(() => {
    api.getStats().then(setStats).catch((e) => setError(e.message))
    api.getSearchLogs({ page_size: '5' }).then((r) => setLogs(r.items)).catch(() => {})
    api.getSystem().then(setSystemInfo).catch(() => {})
    api.getAnalytics(24).then(setAnalytics).catch(() => {})

    const sysInterval = setInterval(() => {
      api.getSystem().then(setSystemInfo).catch(() => {})
    }, 10000)

    const analyticsInterval = setInterval(() => {
      const hours = timeRange === '7d' ? 168 : 24
      api.getAnalytics(hours).then(setAnalytics).catch(() => {})
    }, 30000)

    return () => {
      clearInterval(sysInterval)
      clearInterval(analyticsInterval)
    }
  }, [])

  useEffect(() => {
    const hours = timeRange === '7d' ? 168 : 24
    api.getAnalytics(hours).then(setAnalytics).catch(() => {})
  }, [timeRange])

  if (error) return <div className="p-4 text-red-500">Error: {error}</div>
  if (!stats) return <div className="p-4">Loading...</div>

  const statCards = [
    { label: 'Total Searches', value: stats.total_searches, icon: Search, color: 'text-blue-600' },
    { label: 'Today', value: stats.searches_today, icon: Activity, color: 'text-green-600' },
    { label: 'Active Keys', value: stats.active_keys, icon: Key, color: 'text-purple-600' },
    { label: 'Banned IPs', value: stats.banned_ips, icon: ShieldBan, color: 'text-red-600' },
  ]

  const cpuPct = systemInfo?.cpu_percent ?? null
  const memPct = systemInfo?.memory.percent ?? null

  const successRate = analytics?.success_rate ?? null
  const successColor =
    successRate === null
      ? 'text-gray-400'
      : successRate >= 95
      ? 'text-green-600'
      : successRate >= 80
      ? 'text-yellow-600'
      : 'text-red-600'

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>

      {/* Row 1: Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((c) => (
          <div key={c.label} className="rounded-lg border bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-500">{c.label}</span>
              <c.icon className={`h-5 w-5 ${c.color}`} />
            </div>
            <p className="mt-2 text-3xl font-bold">{c.value}</p>
          </div>
        ))}
      </div>

      {/* Row 2: System monitoring */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-lg border bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-gray-500">CPU</span>
            <Cpu className="h-5 w-5 text-blue-600" />
          </div>
          <p className={`text-3xl font-bold ${cpuPct !== null ? percentColor(cpuPct) : 'text-gray-400'}`}>
            {cpuPct !== null ? `${cpuPct.toFixed(1)}%` : '—'}
          </p>
        </div>

        <div className="rounded-lg border bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-gray-500">Memory</span>
            <HardDrive className="h-5 w-5 text-purple-600" />
          </div>
          <p className={`text-3xl font-bold ${memPct !== null ? percentColor(memPct) : 'text-gray-400'}`}>
            {memPct !== null ? `${memPct.toFixed(1)}%` : '—'}
          </p>
          {systemInfo && (
            <p className="text-xs text-gray-400 mt-1">
              {systemInfo.memory.used_gb.toFixed(1)} / {systemInfo.memory.total_gb.toFixed(1)} GB
            </p>
          )}
        </div>

        <div className="rounded-lg border bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-gray-500">Process</span>
            <Monitor className="h-5 w-5 text-orange-600" />
          </div>
          <p className="text-3xl font-bold text-gray-700">
            {systemInfo ? `${systemInfo.process.rss_mb.toFixed(0)} MB` : '—'}
          </p>
          <p className="text-xs text-gray-400 mt-1">RSS</p>
        </div>

        <div className="rounded-lg border bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-gray-500">Browser Pool</span>
            <Globe className="h-5 w-5 text-teal-600" />
          </div>
          {systemInfo ? (
            <>
              <div className="flex items-center gap-2">
                <span
                  className={`inline-block h-2 w-2 rounded-full ${
                    systemInfo.pool.started ? 'bg-green-500' : 'bg-red-500'
                  }`}
                />
                <p className="text-3xl font-bold text-gray-700">
                  {systemInfo.pool.active_tabs} / {systemInfo.pool.pool_size}
                </p>
              </div>
              <p className="text-xs text-gray-400 mt-1">
                active tabs (max {systemInfo.pool.max_pool_size ?? systemInfo.pool.pool_size})
              </p>
            </>
          ) : (
            <p className="text-3xl font-bold text-gray-400">—</p>
          )}
        </div>
      </div>

      {/* Row 3: Latency chart */}
      <div className="rounded-lg border bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Search Latency</h2>
          <div className="flex gap-2">
            {(['24h', '7d'] as const).map((r) => (
              <button
                key={r}
                onClick={() => setTimeRange(r)}
                className={`px-3 py-1 text-sm rounded-md border transition-colors ${
                  timeRange === r
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'
                }`}
              >
                {r}
              </button>
            ))}
          </div>
        </div>
        {analytics ? (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={analytics.timeline}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="hour" tickFormatter={formatHour} />
              <YAxis unit=" ms" />
              <Tooltip formatter={(v: number) => `${v} ms`} />
              <Line type="monotone" dataKey="avg_ms" stroke="#3b82f6" dot={false} name="Avg" />
              <Line type="monotone" dataKey="p95_ms" stroke="#f97316" dot={false} name="P95" />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-[300px] flex items-center justify-center text-gray-400">Loading...</div>
        )}
      </div>

      {/* Row 4: Engine distribution + success rate */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="rounded-lg border bg-white p-4 shadow-sm">
          <h2 className="text-lg font-semibold mb-4">Engine Distribution</h2>
          {analytics ? (
            analytics.engines.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={analytics.engines} barSize={60}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[250px] flex items-center justify-center text-gray-400 text-sm">
                No engine data yet
              </div>
            )
          ) : (
            <div className="h-[250px] flex items-center justify-center text-gray-400">Loading...</div>
          )}
        </div>

        <div className="rounded-lg border bg-white p-4 shadow-sm flex flex-col items-center justify-center">
          <p className={`text-6xl font-bold ${successColor}`}>
            {successRate !== null ? `${successRate.toFixed(1)}%` : '—'}
          </p>
          <p className="mt-3 text-gray-500 text-sm">Success Rate</p>
        </div>
      </div>

      {/* Row 5: Recent searches */}
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
