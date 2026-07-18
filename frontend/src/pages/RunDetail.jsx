import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getRun, approveRun } from '../api'
import Spinner from '../components/Spinner'

export default function RunDetail() {
  const { runId } = useParams()
  const [run, setRun] = useState(null)
  const [approved, setApproved] = useState(false)
  const [approving, setApproving] = useState(false)

  useEffect(() => {
    getRun(runId).then(setRun).catch(console.error)
  }, [runId])

  async function handleApprove() {
    setApproving(true)
    try {
      await approveRun(runId)
      setApproved(true)
    } catch (e) {
      alert(`Approve failed: ${e.message}`)
    } finally {
      setApproving(false)
    }
  }

  if (!run) return <Spinner />

  const jobs = run.jobs ?? []

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <Link to="/history" className="text-xs text-gray-500 hover:text-gray-300">← History</Link>
          <h2 className="text-2xl font-bold mt-1">Daily Run — {run.date}</h2>
          <p className="text-sm text-gray-400">{jobs.length} jobs · {run.query}</p>
        </div>
        {!approved ? (
          <button
            onClick={handleApprove}
            disabled={approving}
            className="shrink-0 px-4 py-2 bg-green-700 hover:bg-green-600 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors"
          >
            {approving ? 'Generating…' : 'Approve & Generate'}
          </button>
        ) : (
          <span className="text-green-400 text-sm font-medium shrink-0">Packages ready ✓</span>
        )}
      </div>

      {run.summary && (
        <p className="text-sm text-gray-400 bg-gray-800 rounded-lg px-3 py-2">{run.summary}</p>
      )}

      <div className="space-y-4">
        {jobs.map((job, i) => (
          <JobRunCard key={job.id ?? i} job={job} />
        ))}
      </div>
    </div>
  )
}

function JobRunCard({ job }) {
  const [open, setOpen] = useState(false)
  const score = Math.round((job.score ?? 0) * 100)

  return (
    <div className="bg-gray-800 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-700 transition-colors"
      >
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-mono bg-indigo-900 text-indigo-300 px-2 py-0.5 rounded">
            {score}
          </span>
          <span className="font-medium">{job.title}</span>
          <span className="text-gray-400 text-sm">@ {job.company}</span>
          <span className="text-xs text-gray-500">{job.location}</span>
        </div>
        <span className="text-gray-500 text-xs ml-2">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className="border-t border-gray-700 px-4 pb-4 pt-3 space-y-4">
          {job.url && (
            <a
              href={job.url}
              target="_blank"
              rel="noreferrer"
              className="text-xs text-indigo-400 hover:underline"
            >
              View listing →
            </a>
          )}

          {job.resume_tweaks?.length > 0 && (
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-2">Resume Tweaks</p>
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="text-left text-xs text-gray-500 border-b border-gray-700">
                    <th className="pb-1 pr-3 font-normal">Section</th>
                    <th className="pb-1 pr-3 font-normal">Kind</th>
                    <th className="pb-1 font-normal">Suggestion</th>
                  </tr>
                </thead>
                <tbody>
                  {job.resume_tweaks.map((t, i) => (
                    <tr key={i} className="border-b border-gray-700/50">
                      <td className="py-1.5 pr-3 text-gray-400 align-top">{t.section}</td>
                      <td className="py-1.5 pr-3 align-top">
                        <span className="text-xs text-yellow-400 bg-yellow-900/20 px-1.5 py-0.5 rounded">
                          {t.kind}
                        </span>
                      </td>
                      <td className="py-1.5 text-gray-200 align-top">{t.suggested}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {job.cover_letter && (
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-2">Cover Letter</p>
              <p className="text-sm text-gray-300 whitespace-pre-wrap">{job.cover_letter}</p>
            </div>
          )}

          {job.contacts?.length > 0 && (
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wide mb-2">Contacts & Outreach</p>
              <div className="space-y-3">
                {job.contacts.map((c, i) => (
                  <div key={i} className="bg-gray-700/50 rounded-lg p-3 space-y-2">
                    <div className="flex items-center justify-between flex-wrap gap-1">
                      <p className="text-sm font-medium">{c.name}</p>
                      <span className="text-xs text-gray-400">{c.title}</span>
                    </div>
                    {c.email && (
                      <p className="text-xs text-indigo-400">{c.email}</p>
                    )}
                    {c.outreach_body && (
                      <div className="border-l-2 border-gray-600 pl-2">
                        {c.outreach_subject && (
                          <p className="text-xs text-gray-500 mb-1">Subject: {c.outreach_subject}</p>
                        )}
                        <p className="text-xs text-gray-300 whitespace-pre-wrap">{c.outreach_body}</p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
