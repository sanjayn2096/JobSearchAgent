import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { getStatus, listRuns, uploadResume } from '../api'

function timeUntil(isoStr) {
  if (!isoStr) return null
  const diff = new Date(isoStr) - Date.now()
  if (diff <= 0) return 'Any moment now'
  const h = Math.floor(diff / 3600000)
  const m = Math.floor((diff % 3600000) / 60000)
  return `${h}h ${m}m`
}

function fmtPDT(isoStr) {
  if (!isoStr) return ''
  return new Date(isoStr).toLocaleString('en-US', {
    timeZone: 'America/Los_Angeles',
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }) + ' PDT'
}

export default function Dashboard() {
  const [status, setStatus] = useState(null)
  const [lastRun, setLastRun] = useState(null)
  const [query, setQuery] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    getStatus().then(setStatus).catch(console.error)
    listRuns().then(r => setLastRun(r[0] ?? null)).catch(console.error)
    const t = setInterval(() => setStatus(s => s ? { ...s } : s), 60000)
    return () => clearInterval(t)
  }, [])

  async function handleUpload(e) {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      const result = await uploadResume(file)
      alert(`Resume uploaded — ${result.headline}`)
      const s = await getStatus()
      setStatus(s)
    } catch (err) {
      alert(`Upload failed: ${err.message}`)
    }
    e.target.value = ''
  }

  function handleSearch(e) {
    e.preventDefault()
    if (query.trim()) navigate(`/search?q=${encodeURIComponent(query.trim())}`)
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h2 className="text-2xl font-bold">Dashboard</h2>

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-gray-800 rounded-xl p-4 space-y-1">
          <p className="text-xs text-gray-500 uppercase tracking-wide">Next Daily Run</p>
          <p className="text-2xl font-mono text-indigo-400">
            {status ? (timeUntil(status.next_run_utc) ?? '—') : '…'}
          </p>
          <p className="text-xs text-gray-500">{fmtPDT(status?.next_run_utc)}</p>
        </div>

        <div className="bg-gray-800 rounded-xl p-4 space-y-2">
          <p className="text-xs text-gray-500 uppercase tracking-wide">Resume</p>
          {status?.has_resume ? (
            <p className="text-green-400 font-medium text-sm">Uploaded</p>
          ) : (
            <p className="text-yellow-400 font-medium text-sm">Not uploaded</p>
          )}
          <label className="cursor-pointer">
            <span className="text-xs text-indigo-400 hover:underline">
              {status?.has_resume ? 'Replace resume' : 'Upload PDF / DOCX'}
            </span>
            <input
              type="file"
              accept=".pdf,.docx"
              className="hidden"
              onChange={handleUpload}
            />
          </label>
        </div>
      </div>

      <form onSubmit={handleSearch} className="bg-gray-800 rounded-xl p-4 space-y-3">
        <p className="text-xs text-gray-500 uppercase tracking-wide">Quick Search</p>
        <div className="flex gap-2">
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder={status?.daily_query ?? 'e.g. Senior Android engineer remote'}
            className="flex-1 bg-gray-700 rounded-lg px-3 py-2 text-sm placeholder-gray-500 outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <button
            type="submit"
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-sm font-medium transition-colors"
          >
            Search
          </button>
        </div>
      </form>

      {lastRun ? (
        <div className="bg-gray-800 rounded-xl p-4 flex items-center justify-between">
          <div className="space-y-0.5">
            <p className="text-xs text-gray-500 uppercase tracking-wide">Last Daily Run</p>
            <p className="font-medium">{lastRun.date} · {lastRun.job_count} jobs</p>
            {lastRun.top_job && <p className="text-sm text-gray-400">{lastRun.top_job}</p>}
          </div>
          <Link to={`/runs/${lastRun.run_id}`} className="text-sm text-indigo-400 hover:underline">
            View →
          </Link>
        </div>
      ) : (
        status !== null && (
          <p className="text-sm text-gray-500 text-center py-4">
            No daily runs yet. Upload your resume and wait for 8 AM PDT, or use Quick Search above.
          </p>
        )
      )}
    </div>
  )
}
