import { Routes, Route } from 'react-router-dom'
import Nav from './components/Nav'
import Dashboard from './pages/Dashboard'
import Search from './pages/Search'
import History from './pages/History'
import RunDetail from './pages/RunDetail'

export default function App() {
  return (
    <div className="flex h-screen bg-gray-950 text-gray-100">
      <Nav />
      <main className="flex-1 overflow-auto p-6">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/search" element={<Search />} />
          <Route path="/history" element={<History />} />
          <Route path="/runs/:runId" element={<RunDetail />} />
        </Routes>
      </main>
    </div>
  )
}
