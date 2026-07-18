import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { listRuns } from '../api'
import Spinner from '../components/Spinner'

export default function History() {
  const [runs, setRuns] = useState(null)

  useEffect(() => {
    listRuns().then(setRuns).catch(console.error)
  }, [])

  if (!runs) return <Spinner />

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h2 className="text-2xl font-bold">Run History</h2>

      {runs.length === 0 ? (
        <p className="text-gray-500 text-sm">No daily runs yet.</p>
      ) : (
        <div className="bg-gray-800 rounded-xl divide-y divide-gray-700">
          {runs.map(run => (
            <div key={run.run_id} className="flex items-center justify-between px-4 py-3">
              <div className="space-y-0.5">
                <p className="font-medium">{run.date}</p>
                <p className="text-sm text-gray-400">
                  {run.job_count} jobs{run.top_job ? ` · ${run.top_job}` : ''}
                </p>
                {run.query && (
                  <p className="text-xs text-gray-600 truncate max-w-xs">{run.query}</p>
                )}
              </div>
              <Link
                to={`/runs/${run.run_id}`}
                className="text-sm text-indigo-400 hover:underline shrink-0 ml-4"
              >
                View →
              </Link>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
