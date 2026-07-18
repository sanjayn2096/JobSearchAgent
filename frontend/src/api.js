const B = '/api/v1'

async function req(path, opts = {}) {
  const res = await fetch(B + path, opts)
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || res.statusText)
  }
  return res.json()
}

export const getStatus = () => req('/status')
export const listRuns = () => req('/runs')
export const getRun = id => req(`/runs/${id}`)
export const approveRun = id => req(`/approve/${id}`, { method: 'POST' })

export const searchJobs = (query) =>
  req('/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, include_cover_letters: true }),
  })

export async function uploadResume(file) {
  const fd = new FormData()
  fd.append('file', file)
  return req('/resume', { method: 'POST', body: fd })
}

export const analyzeResume = (jobs) =>
  req('/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jobs }),
  })
