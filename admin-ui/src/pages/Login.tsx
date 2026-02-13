import { useState } from 'react'
import { setToken } from '@/lib/api'

export default function Login({ onLogin }: { onLogin: () => void }) {
  const [token, setTokenValue] = useState('')
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setToken(token)
    try {
      const res = await fetch('/admin/api/stats', {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) {
        onLogin()
      } else {
        setError('Invalid admin token')
      }
    } catch {
      setError('Connection failed')
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <form onSubmit={handleSubmit} className="w-full max-w-sm rounded-lg border bg-white p-6 shadow-sm space-y-4">
        <h1 className="text-xl font-bold text-center">WSM Admin</h1>
        <input
          type="password"
          className="w-full rounded border px-3 py-2 text-sm"
          placeholder="Admin Token"
          value={token}
          onChange={(e) => setTokenValue(e.target.value)}
        />
        {error && <p className="text-sm text-red-500">{error}</p>}
        <button type="submit" className="w-full rounded bg-blue-600 py-2 text-sm text-white hover:bg-blue-700">
          Sign In
        </button>
      </form>
    </div>
  )
}
