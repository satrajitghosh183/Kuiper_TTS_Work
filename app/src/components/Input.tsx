import { InputHTMLAttributes, forwardRef } from 'react'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  hint?: string
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, hint, className = '', ...props }, ref) => {
    const baseStyles = `
      w-full bg-surface border rounded-lg
      px-4 py-3 text-text-primary placeholder:text-text-muted
      transition-all duration-fast ease-default
      focus:outline-none
    `

    const stateStyles = error
      ? 'border-accent bg-accent/5 focus:border-accent focus:shadow-glow'
      : 'border-border focus:border-accent focus:shadow-glow'

    return (
      <div className="space-y-1">
        {label && (
          <label className="block text-caption text-text-secondary">
            {label}
          </label>
        )}
        <input
          ref={ref}
          className={`${baseStyles} ${stateStyles} ${className}`}
          {...props}
        />
        {error && (
          <p className="text-caption text-accent">{error}</p>
        )}
        {hint && !error && (
          <p className="text-caption text-text-muted">{hint}</p>
        )}
      </div>
    )
  }
)

Input.displayName = 'Input'

