import { forwardRef, ReactNode } from 'react'
import { motion } from 'framer-motion'

interface CardProps {
  children?: ReactNode
  variant?: 'default' | 'elevated'
  hoverable?: boolean
  className?: string
  onClick?: () => void
}

export const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ children, variant = 'default', hoverable = false, className = '', onClick }, ref) => {
    const baseStyles = `
      bg-surface border border-border rounded-lg p-md
      transition-all duration-standard ease-default
    `

    const variants = {
      default: '',
      elevated: 'shadow-card',
    }

    const hoverStyles = hoverable
      ? 'hover:-translate-y-0.5 hover:shadow-card-hover cursor-pointer'
      : ''

    return (
      <motion.div
        ref={ref}
        className={`${baseStyles} ${variants[variant]} ${hoverStyles} ${className}`}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2, ease: [0.25, 0.1, 0.25, 1] }}
        onClick={onClick}
      >
        {children}
      </motion.div>
    )
  }
)

Card.displayName = 'Card'

