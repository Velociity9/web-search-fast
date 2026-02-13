import { useEffect, useState, useCallback } from 'react'
import { api, type IPBan } from '@/lib/api'

export default function IPMonitor() {
  const [bans, setBans] = useState<IPBan[]>([])
  const [ip, setIp] = useState('')
  const [reason, setReason] = useState('')

  const load = useCallback(() => {
    api.getBans().then(setBans).catch(() => {})
  }, [])

  useEffect(() => { load() }, [load])

  const handleBan = async () => {
    if (!ip.trim()) return
    await api.banIP({ ip: ip.trim(), reason })
    setIp(''); setReason('')
    load()
  }

  const handleUnban = async (banIp: string) => {
    await api.unbanIP(banIp)
    load()
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">IP Monitor</h1>
      <div className="flex gap-2">
        <input className="rounded border px-3 py-1.5 text-sm" placeholder="IP address" value={ip} onChange={(e) => setIp(e.target.value)} />
        <input className="rounded border px-3 py-1.5 text-sm flex-1" placeholder="Reason (optional)" value={reason} onChange={(e) => setReason(e.target.value)} />
        <button className="rounded bg-red-600 px-4 py-1.5 text-sm text-white hover:bg-red-700" onClick={handleBan}>Ban IP</button>
      </div>
      <div className="rounded-lg border bg-white shadow-sm">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-gray-50 text-left text-gray-500">
              <th className="p-3">IP Address</th>
              <th className="p-3">Reason</th>
              <th className="p-3">Banned At</th>
              <th className="p-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {bans.length === 0 && (
              <tr><td colSpan={4} className="p-3 text-center text-gray-400">No banned IPs</td></tr>
            )}
            {bans.map((b) => (
              <tr key={b.id} className="border-b last:border-0 hover:bg-gray-50">
                <td className="p-3 font-mono">{b.ip_address}</td>
                <td className="p-3">{b.reason || '-'}</td>
                <td className="p-3 text-gray-400">{new Date(b.created_at).toLocaleString()}</td>
                <td className="p-3">
                  <button className="rounded border px-2 py-1 text-xs text-red-600 hover:bg-red-50" onClick={() => handleUnban(b.ip_address)}>Unban</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
