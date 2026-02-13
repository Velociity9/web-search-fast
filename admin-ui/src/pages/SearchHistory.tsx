import { useEffect, useState, useCallback } from 'react'
import { api, type SearchLog } from '@/lib/api'

export default function SearchHistory() {
  const [logs, setLogs] = useState<SearchLog[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [ipFilter, setIpFilter] = useState('')
  const [queryFilter, setQueryFilter] = useState('')

  const load = useCallback(() => {
    const params: Record<string, string> = { page: String(page), page_size: '20' }
    if (ipFilter) params.ip = ipFilter
    if (queryFilter) params.query = queryFilter
    api.getSearchLogs(params).then((r) => { setLogs(r.items); setTotal(r.total) }).catch(() => {})
  }, [page, ipFilter, queryFilter])

  useEffect(() => { load() }, [load])

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Search History</h1>
      <div className="flex gap-2">
        <input
          className="rounded border px-3 py-1.5 text-sm"
          placeholder="Filter by query..."
          value={queryFilter}
          onChange={(e) => { setQueryFilter(e.target.value); setPage(1) }}
        />
        <input
          className="rounded border px-3 py-1.5 text-sm"
          placeholder="Filter by IP..."
          value={ipFilter}
          onChange={(e) => { setIpFilter(e.target.value); setPage(1) }}
        />
      </div>
      <div className="rounded-lg border bg-white shadow-sm overflow-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-gray-50 text-left text-gray-500">
              <th className="p-3">Query</th>
              <th className="p-3">Engine</th>
              <th className="p-3">IP</th>
              <th className="p-3">Status</th>
              <th className="p-3">Latency</th>
              <th className="p-3">Time</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((l) => (
              <tr key={l.id} className="border-b last:border-0 hover:bg-gray-50">
                <td className="p-3 font-medium max-w-xs truncate">{l.query}</td>
                <td className="p-3">{l.engine || '-'}</td>
                <td className="p-3 font-mono text-xs">{l.ip_address}</td>
                <td className="p-3">{l.status_code ?? '-'}</td>
                <td className="p-3">{l.elapsed_ms ? `${l.elapsed_ms}ms` : '-'}</td>
                <td className="p-3 text-gray-400">{new Date(l.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between text-sm">
        <span className="text-gray-500">Total: {total}</span>
        <div className="flex gap-2">
          <button className="rounded border px-3 py-1 disabled:opacity-50" disabled={page <= 1} onClick={() => setPage(page - 1)}>Prev</button>
          <span className="px-2 py-1">Page {page}</span>
          <button className="rounded border px-3 py-1 disabled:opacity-50" disabled={logs.length < 20} onClick={() => setPage(page + 1)}>Next</button>
        </div>
      </div>
    </div>
  )
}
