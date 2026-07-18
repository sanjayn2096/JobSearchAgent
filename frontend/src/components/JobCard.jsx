import { useState } from 'react'

function fmtSalary(sal) {
  if (!sal || (!sal.minimum && !sal.maximum)) return null
  const fmt = v => v >= 1000 ? `$${Math.round(v / 1000)}k` : `$${v}`
  return sal.minimum && sal.maximum
    ? `${fmt(sal.minimum)} – ${fmt(sal.maximum)}`
    : fmt(sal.minimum || sal.maximum)
}

export default function JobCard({ item }) {
  const [open, setOpen] = useState(false)
  const job = item.job
  const score = Math.round((item.score ?? 0) * 100)
  const salStr = fmtSalary(job.salary)

  return (
    <div className="bg-gray-800 rounded-xl overflow-hidden">
      <div className="px-4 py-3 space-y-1">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-mono bg-indigo-900 text-indigo-300 px-2 py-0.5 rounded">
              {score}
            </span>
            <span className="text-gray-100 font-medium">{job.title}</span>
          </div>
          {job.url && (
            <a
              href={job.url}
              target="_blank"
              rel="noreferrer"
              className="text-xs text-indigo-400 hover:underline shrink-0"
            >
              Apply →
            </a>
          )}
        </div>
        <p className="text-sm text-gray-400">
          {job.company}{job.location ? ` · ${job.location}` : ''}
          {job.posted_at && (
            <span className="ml-2 text-xs text-gray-600">
              · {new Date(job.posted_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
            </span>
          )}
        </p>
        {salStr && <p className="text-sm text-green-400">{salStr}</p>}
        {job.skills?.length > 0 && (
          <div className="flex flex-wrap gap-1 pt-1">
            {job.skills.slice(0, 6).map(s => (
              <span key={s} className="text-xs bg-gray-700 text-gray-300 px-2 py-0.5 rounded">
                {s}
              </span>
            ))}
          </div>
        )}
        {item.missing_skills?.length > 0 && (
          <p className="text-xs text-gray-500">
            Missing: {item.missing_skills.slice(0, 4).join(', ')}
          </p>
        )}
      </div>

      {item.cover_letter && (
        <>
          <button
            onClick={() => setOpen(o => !o)}
            className="w-full text-left px-4 py-2 text-xs text-indigo-400 border-t border-gray-700 hover:bg-gray-700 transition-colors"
          >
            {open ? '▲ Hide cover letter' : '▼ View cover letter'}
          </button>
          {open && (
            <div className="px-4 pb-3 pt-2 text-sm text-gray-300 whitespace-pre-wrap border-t border-gray-700">
              {item.cover_letter}
            </div>
          )}
        </>
      )}
    </div>
  )
}
