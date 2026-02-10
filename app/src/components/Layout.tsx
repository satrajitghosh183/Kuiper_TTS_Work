import { ReactNode } from 'react'
import { useLocation, Link } from 'react-router-dom'
import { Mic, Settings, Play, Cpu, FlaskConical } from 'lucide-react'

interface LayoutProps {
  children: ReactNode
}

const navItems = [
  { path: '/', icon: Mic, label: 'Record' },
  { path: '/setup', icon: Settings, label: 'Setup' },
  { path: '/train', icon: FlaskConical, label: 'Train' },
  { path: '/test', icon: Play, label: 'Test' },
  { path: '/welcome', icon: Cpu, label: 'System' },
]

export function Layout({ children }: LayoutProps) {
  const location = useLocation()

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <aside className="w-16 bg-surface border-r border-border flex flex-col">
        {/* Logo area */}
        <div className="h-16 flex items-center justify-center border-b border-border draggable">
          <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center no-drag">
            <span className="text-text-primary font-bold text-sm">K</span>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-4">
          <ul className="space-y-2 px-2">
            {navItems.map(({ path, icon: Icon, label }) => {
              const isActive = location.pathname === path
              return (
                <li key={path}>
                  <Link
                    to={path}
                    className={`
                      w-12 h-12 rounded-lg flex items-center justify-center
                      transition-all duration-fast ease-default
                      group relative
                      ${isActive 
                        ? 'bg-accent/10 text-accent' 
                        : 'text-text-secondary hover:text-text-primary hover:bg-surface'
                      }
                    `}
                    title={label}
                  >
                    <Icon size={20} strokeWidth={1.5} />
                    
                    {/* Tooltip */}
                    <span className="
                      absolute left-full ml-2 px-2 py-1
                      bg-surface border border-border rounded
                      text-caption text-text-primary
                      opacity-0 group-hover:opacity-100
                      pointer-events-none
                      transition-opacity duration-fast
                      whitespace-nowrap
                      z-50
                    ">
                      {label}
                    </span>
                  </Link>
                </li>
              )
            })}
          </ul>
        </nav>

        {/* Version */}
        <div className="p-2 text-center">
          <span className="text-micro text-text-muted font-mono">v1.0.0</span>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        {/* Draggable title bar area */}
        <div className="h-8 draggable" />
        
        {/* Content */}
        <div className="px-xl pb-xl">
          {children}
        </div>
      </main>
    </div>
  )
}

