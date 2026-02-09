import { forwardRef } from 'react'

interface ToggleProps {
  label: string
  checked: boolean
  onChange: (checked: boolean) => void
  disabled?: boolean
  className?: string
}

export const Toggle = forwardRef<HTMLInputElement, ToggleProps>(
  ({ label, checked, onChange, disabled = false, className = '' }, ref) => {
    return (
      <label className={`flex items-center justify-between cursor-pointer ${disabled ? 'opacity-50 cursor-not-allowed' : ''} ${className}`}>
        <span className="text-body text-text-primary">{label}</span>
        <div className="relative">
          <input
            ref={ref}
            type="checkbox"
            checked={checked}
            onChange={(e) => onChange(e.target.checked)}
            disabled={disabled}
            className="sr-only"
            aria-label={label}
          />
          <div
            className={`
              w-11 h-6 rounded-full transition-colors duration-fast
              ${checked ? 'bg-accent' : 'bg-border'}
              ${disabled ? 'opacity-50' : ''}
            `}
          >
            <div
              className={`
                absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white
                transition-transform duration-fast
                ${checked ? 'translate-x-5' : 'translate-x-0'}
              `}
            />
          </div>
        </div>
      </label>
    )
  }
)

Toggle.displayName = 'Toggle'
