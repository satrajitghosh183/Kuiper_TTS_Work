import { useRef, useState, useEffect } from 'react'

interface VirtualListProps<T> {
  items: T[]
  renderItem: (item: T, index: number) => React.ReactNode
  estimateSize?: number
  overscan?: number
  className?: string
}

export function VirtualList<T>({ 
  items, 
  renderItem, 
  estimateSize = 50,
  overscan = 5,
  className = ''
}: VirtualListProps<T>) {
  const containerRef = useRef<HTMLDivElement>(null)
  
  // Simple virtual scrolling implementation
  // For production, consider using @tanstack/react-virtual for better performance
  const [visibleRange, setVisibleRange] = useState({ start: 0, end: Math.min(items.length, 20) })
  
  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const handleScroll = () => {
      const scrollTop = container.scrollTop
      const containerHeight = container.clientHeight
      
      const start = Math.max(0, Math.floor(scrollTop / estimateSize) - overscan)
      const end = Math.min(
        items.length,
        Math.ceil((scrollTop + containerHeight) / estimateSize) + overscan
      )
      
      setVisibleRange({ start, end })
    }

    container.addEventListener('scroll', handleScroll)
    handleScroll() // Initial calculation
    
    return () => container.removeEventListener('scroll', handleScroll)
  }, [items.length, estimateSize, overscan])
  
  const visibleItems = items.slice(visibleRange.start, visibleRange.end)
  const totalHeight = items.length * estimateSize
  const offsetY = visibleRange.start * estimateSize
  
  return (
    <div 
      ref={containerRef}
      className={`h-full overflow-auto ${className}`}
    >
      <div style={{ height: `${totalHeight}px`, position: 'relative' }}>
        <div style={{ transform: `translateY(${offsetY}px)` }}>
          {visibleItems.map((item, index) => (
            <div
              key={visibleRange.start + index}
              style={{ height: `${estimateSize}px` }}
            >
              {renderItem(item, visibleRange.start + index)}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
