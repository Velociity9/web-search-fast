import { useEffect, useState, useCallback } from 'react'
import { api, type APIKey, type APIKeyCreated } from '@/lib/api'

export default function APIKeys() {
  const [keys, setKeys] = useState<APIKey[]>([])
  const [name, setName] = useState('')
  const [limit, setLimit] = useState('0')
  const [created, setCreated] = useState<APIKeyCreated | null>(null)

  const load = useCallback(() => {
    api.getKeys().then(setKeys).catch(() => {})
  }, [])

  useEffect(() => { load() }, [load])

  const handleCreate = async () => {
    if (!name.trim()) return
    const key = await api.createKey({ name: name.trim(), call_limit: parseInt(limit) || 0 })
    setCreated(key)
    setName(''); setLimit('0')
    load()
  }

  const handleRevoke = async (id: string) => {
    await api.deleteKey(id)
    load()
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">API Keys</h1>

      {created && (
        <div className="rounded-lg border border-green-200 bg-green-50 p-4">
          <p className="text-sm font-medium text-green-800">Key created! Copy it now — it won't be shown again:</p>
          <code className="mt-1 block rounded bg-white p-2 text-sm font-mono break-all select-all">{created.key}</code>
          <button className="mt-2 text-xs text-green-600 underline" onClick={() => setCreated(null)}>Dismiss</button>
        </div>
      )}

      <div className="flex gap-2">
        <input className="rounded border px-3 py-1.5 text-sm flex-1" placeholder="Key name" value={name} onChange={(e) => setName(e.target.value)} />
        <input className="rounded border px-3 py-1.5 text-sm w-32" type="number" placeholder="Call limit (0=∞)" value={limit} onChange={(e) => setLimit(e.target.value)} />
        <button className="rounded bg-blue-600 px-4 py-1.5 text-sm text-white hover:bg-blue-700" onClick={handleCreate}>Create Key</button>
      </div>

      <div className="rounded-lg border bg-white shadow-sm">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-gray-50 text-left text-gray-500">
              <th className="p-3">Name</th>
              <th className="p-3">Prefix</th>
              <th className="p-3">Calls</th>
              <th className="p-3">Limit</th>
              <th className="p-3">Status</th>
              <th className="p-3">Created</th>
              <th className="p-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {keys.length === 0 && (
              <tr><td colSpan={7} className="p-3 text-center text-gray-400">No API keys</td></tr>
            )}
            {keys.map((k) => (
              <tr key={k.id} className="border-b last:border-0 hover:bg-gray-50">
                <td className="p-3 font-medium">{k.name}</td>
                <td className="p-3 font-mono text-xs">{k.key_prefix}...</td>
                <td className="p-3">{k.call_count}</td>
                <td className="p-3">{k.call_limit === 0 ? '∞' : k.call_limit}</td>
                <td className="p-3">
                  <span className={`inline-block rounded-full px-2 py-0.5 text-xs ${k.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                    {k.is_active ? 'Active' : 'Revoked'}
                  </span>
                </td>
                <td className="p-3 text-gray-400">{new Date(k.created_at).toLocaleString()}</td>
                <td className="p-3">
                  {k.is_active && (
                    <button className="rounded border px-2 py-1 text-xs text-red-600 hover:bg-red-50" onClick={() => handleRevoke(k.id)}>Revoke</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
