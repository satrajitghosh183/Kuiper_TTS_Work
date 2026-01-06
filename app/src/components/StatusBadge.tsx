import { Check, X, AlertTriangle, Loader2 } from 'lucide-react'

type Status = 'success' | 'error' | 'warning' | 'loading' | 'idle'

interface StatusBadgeProps {
  status: Status
  label?: string
  className?: string
}

export function StatusBadge({ status, label, className = '' }: StatusBadgeProps) {
  const config = {
    success: {
      icon: Check,
      bg: 'bg-green-500/10',
      text: 'text-green-400',
      border: 'border-green-500/20',
    },
    error: {
      icon: X,
      bg: 'bg-accent/10',
      text: 'text-accent',
      border: 'border-accent/20',
    },
    warning: {
      icon: AlertTriangle,
      bg: 'bg-yellow-500/10',
      text: 'text-yellow-400',
      border: 'border-yellow-500/20',
    },
    loading: {
      icon: Loader2,
      bg: 'bg-blue-500/10',
      text: 'text-blue-400',
      border: 'border-blue-500/20',
    },
    idle: {
      icon: null,
      bg: 'bg-surface',
      text: 'text-text-muted',
      border: 'border-border',
    },
  }

  const { icon: Icon, bg, text, border } = config[status]

  return (
    <span
      className={`
        inline-flex items-center gap-1.5 px-2 py-1
        rounded border ${bg} ${text} ${border}
        text-caption font-medium
        ${className}
      `}
    >
      {Icon && (
        <Icon 
          size={14} 
          className={status === 'loading' ? 'animate-spin' : ''} 
        />
      )}
      {label}
    </span>
  )
}

