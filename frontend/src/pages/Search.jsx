import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { searchJobs, analyzeResume } from '../api'
import JobCard from '../components/JobCard'
import Spinner from '../components/Spinner'

export default function Search() {
  const [params] = useSearchParams()
  const [query, setQuery] = useState(params.get('q') ?? '')
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [tweaks, setTweaks] = useState({})
  const [analyzing, setAnalyzing] = useState(false)

  useEffect(() => {
    const q = params.get('q')
    if (q) runSearch(q)
  }, [])

  async function runSearch(q) {
    setLoading(true)
    setError(null)
    setResults(null)
    setTweaks({})
    try {
      const data = await searchJobs(q ?? query)
      setResults(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  function handleSubmit(e) {
    e.preventDefault()
    if (query.trim()) runSearch(query.trim())
  }

  async function handleAnalyze() {
    if (!results?.results?.length) return
    setAnalyzing(true)
    try {
      const jobs = results.results.slice(0, 5).map(item => ({
        id: item.job.id,
        title: item.job.title,
        company: item.job.company,
        location: item.job.location ?? '',
        skills: item.job.skills ?? [],
        missing_skills: item.missing_skills ?? [],
        score: item.score ?? 0,
      }))
      const data = await analyzeResume(jobs)
      setTweaks(data)
    } catch (e) {
      alert(`Analysis failed: ${e.message}`)
    } finally {
      setAnalyzing(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h2 className="text-2xl font-bold">Search Jobs</h2>

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Senior Android engineer remote..."
          className="flex-1 bg-gray-800 rounded-lg px-3 py-2 text-sm placeholder-gray-500 outline-none focus:ring-2 focus:ring-indigo-500"
        />
        <button
          type="submit"
          disabled={loading}
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors"
        >
          {loading ? 'Searching…' : 'Search'}
        </button>
      </form>

      {error && <p className="text-red-400 text-sm bg-red-900/20 rounded-lg px-3 py-2">{error}</p>}
      {loading && <Spinner />}

      {results && !loading && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-500">
              {results.total_found} jobs found · {results.results.length} shown
            </p>
            <button
              onClick={handleAnalyze}
              disabled={analyzing}
              className="px-3 py-1.5 bg-purple-700 hover:bg-purple-600 disabled:opacity-50 rounded-lg text-xs font-medium transition-colors"
            >
              {analyzing ? 'Analyzing…' : '✦ Analyze for my resume'}
            </button>
          </div>

          {results.summary && (
            <p className="text-sm text-gray-400 bg-gray-800 rounded-lg px-3 py-2">{results.summary}</p>
          )}

          {results.results.map((item, i) => (
            <JobCard
              key={item.job?.id ?? i}
              item={item}
              tweaks={tweaks[item.job?.id] ?? null}
            />
          ))}
        </div>
      )}
    </div>
  )
}
