import { useState } from 'react'
import { Search } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'

const PAGE_TITLES: Record<string, string> = {
  '/': 'Dashboard',
  '/startups': 'Startups',
  '/batches': 'Lotes de Processamento',
  '/login': 'Login',
}

export function Header() {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const title = Object.entries(PAGE_TITLES)
    .sort((a, b) => b[0].length - a[0].length)
    .find(([path]) => pathname === path || pathname.startsWith(`${path}/`))?.[1] ?? 'NVIDIA AI Radar'

  return (
    <header className="app-header">
      <div>
        <h1 style={{ fontSize: '1.15rem' }}>{title}</h1>
        <p className="header-subtitle">NVIDIA Startup AI Radar - Inception Intelligence</p>
      </div>
      <form
        className="header-search"
        onSubmit={(event) => {
          event.preventDefault()
          const query = search.trim()
          navigate(query ? `/startups?q=${encodeURIComponent(query)}` : '/startups')
        }}
      >
        <Search size={14} aria-hidden="true" />
        <input
          className="input input-sm"
          placeholder="Buscar startup..."
          aria-label="Buscar startup"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </form>
    </header>
  )
}
