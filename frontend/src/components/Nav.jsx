import { NavLink } from 'react-router-dom'

const links = [
  { to: '/', label: 'Dashboard', icon: '⬡', end: true },
  { to: '/search', label: 'Search', icon: '⌕' },
  { to: '/history', label: 'History', icon: '◷' },
]

export default function Nav() {
  return (
    <nav className="w-44 shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col p-4 gap-1">
      <p className="text-indigo-400 font-bold text-base mb-6 px-2">Job Agent</p>
      {links.map(l => (
        <NavLink
          key={l.to}
          to={l.to}
          end={l.end}
          className={({ isActive }) =>
            `px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
              isActive
                ? 'bg-indigo-600 text-white'
                : 'text-gray-400 hover:bg-gray-800 hover:text-gray-100'
            }`
          }
        >
          {l.icon} {l.label}
        </NavLink>
      ))}
    </nav>
  )
}
