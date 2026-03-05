import { useState, ReactNode } from 'react'
import { useLocation, Link } from 'react-router-dom'
import { Mic, Settings, Play, Cpu, FlaskConical, Menu, X } from 'lucide-react'

interface LayoutProps {
  children: ReactNode
}

const navItems = [
  { path: '/', icon: Cpu, label: 'Welcome' },
  { path: '/record', icon: Mic, label: 'Record' },
  { path: '/setup', icon: Settings, label: 'Setup' },
  { path: '/train', icon: FlaskConical, label: 'Train' },
  { path: '/test', icon: Play, label: 'Test' },
]

export function Layout({ children }: LayoutProps) {
  const location = useLocation()
  const [navOpen, setNavOpen] = useState(false)

  return (
    <div className="flex flex-col sm:flex-row min-h-screen h-screen bg-background">
      {/* Mobile: top bar with menu toggle */}
      <header className="sm:hidden flex items-center justify-between h-14 px-4 border-b border-border bg-surface draggable">
        <button
          type="button"
          onClick={() => setNavOpen(!navOpen)}
          className="p-2 -ml-2 rounded-lg text-text-secondary hover:text-text-primary no-drag"
          aria-label={navOpen ? 'Close menu' : 'Open menu'}
        >
          {navOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
        <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center no-drag">
          <span className="text-text-primary font-bold text-sm">K</span>
        </div>
        <div className="w-10" />
      </header>

      {/* Sidebar: hidden on mobile unless open, always visible on desktop */}
      <aside
        className={`
          bg-surface border-r border-border flex flex-col
          fixed sm:relative inset-y-0 left-0 z-40
          w-64 sm:w-16
          transform transition-transform duration-200 ease-out
          ${navOpen ? 'translate-x-0' : '-translate-x-full sm:translate-x-0'}
        `}
      >
        <div className="h-14 sm:h-16 flex items-center justify-between sm:justify-center border-b border-border px-4 sm:px-0 draggable">
          <span className="text-text-primary font-semibold sm:hidden">Menu</span>
          <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center no-drag">
            <span className="text-text-primary font-bold text-sm">K</span>
          </div>
          <button
            type="button"
            onClick={() => setNavOpen(false)}
            className="sm:hidden p-2 rounded-lg text-text-secondary hover:text-text-primary"
            aria-label="Close menu"
          >
            <X size={20} />
          </button>
        </div>

        <nav className="flex-1 py-4 overflow-y-auto">
          <ul className="space-y-1 px-2">
            {navItems.map(({ path, icon: Icon, label }) => {
              const isActive = location.pathname === path
              return (
                <li key={path}>
                  <Link
                    to={path}
                    onClick={() => setNavOpen(false)}
                    className={`
                      flex items-center gap-3 sm:justify-center w-full sm:w-12 h-12 rounded-lg px-3 sm:px-0
                      transition-all duration-fast ease-default
                      group relative
                      min-h-[44px] sm:min-h-0
                      ${isActive 
                        ? 'bg-accent/10 text-accent' 
                        : 'text-text-secondary hover:text-text-primary hover:bg-surface'
                      }
                    `}
                    title={label}
                  >
                    <Icon size={20} strokeWidth={1.5} className="flex-shrink-0" />
                    <span className="sm:hidden text-body">{label}</span>
                    <span className="
                      hidden sm:block absolute left-full ml-2 px-2 py-1
                      bg-surface border border-border rounded
                      text-caption text-text-primary
                      opacity-0 group-hover:opacity-100
                      pointer-events-none transition-opacity duration-fast
                      whitespace-nowrap z-50
                    ">
                      {label}
                    </span>
                  </Link>
                </li>
              )
            })}
          </ul>
        </nav>

        <div className="p-2 text-center border-t border-border">
          <span className="text-micro text-text-muted font-mono">v1.0.0</span>
        </div>
      </aside>

      {/* Mobile: backdrop when nav open */}
      {navOpen && (
        <div
          className="sm:hidden fixed inset-0 bg-black/50 z-30"
          onClick={() => setNavOpen(false)}
          onKeyDown={(e) => e.key === 'Escape' && setNavOpen(false)}
          role="button"
          tabIndex={0}
          aria-label="Close menu"
        />
      )}

      {/* Main content */}
      <main className="flex-1 overflow-auto flex flex-col min-w-0">
        <div className="h-8 draggable hidden sm:block" />
        <div className="flex-1 px-4 sm:px-xl pb-4 sm:pb-xl container-responsive max-w-full">
          {children}
        </div>
      </main>
    </div>
  )
}

