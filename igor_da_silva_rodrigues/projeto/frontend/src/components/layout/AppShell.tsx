import React from 'react'
import { LayoutDashboard, Layers, Rocket } from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Header } from './Header'

export const AppShell: React.FC = () => (
  <div className="app-shell">
    <Sidebar />
    <div className="main-content">
      <Header />
      <main className="page-content">
        <Outlet />
      </main>
    </div>
    <nav className="mobile-nav" aria-label="Navegacao principal">
      <NavLink to="/" end><LayoutDashboard size={18} /><span>Dashboard</span></NavLink>
      <NavLink to="/startups"><Rocket size={18} /><span>Startups</span></NavLink>
      <NavLink to="/batches"><Layers size={18} /><span>Lotes</span></NavLink>
    </nav>
  </div>
)
