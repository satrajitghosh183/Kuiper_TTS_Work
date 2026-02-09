import { useState, ReactNode } from 'react'
import { useMediaQuery } from '../hooks/useMediaQuery'

interface ResponsiveLayoutProps {
  children: ReactNode
  sidebar?: ReactNode
  mobileSidebar?: 'bottom' | 'drawer' | 'none'
}

export function ResponsiveLayout({ children, sidebar, mobileSidebar = 'drawer' }: ResponsiveLayoutProps) {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)
  const isMobile = useMediaQuery('(max-width: 640px)')
  
  return (
    <div className="flex flex-col md:flex-row h-screen">
      {/* Desktop sidebar */}
      {sidebar && (
        <aside className="hidden md:block w-16 border-r border-border">
          {sidebar}
        </aside>
      )}
      
      {/* Mobile drawer - simplified for now, can be enhanced with Drawer component later */}
      {isMobile && mobileSidebar === 'drawer' && sidebar && isMobileMenuOpen && (
        <div className="fixed inset-0 z-50 bg-black/50" onClick={() => setIsMobileMenuOpen(false)}>
          <div className="w-64 h-full bg-surface border-r border-border" onClick={(e) => e.stopPropagation()}>
            {sidebar}
          </div>
        </div>
      )}
      
      {/* Main content */}
      <main className="flex-1 overflow-auto container-responsive">
        {children}
      </main>
    </div>
  )
}
