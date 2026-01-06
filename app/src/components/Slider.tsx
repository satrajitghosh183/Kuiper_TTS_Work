import { InputHTMLAttributes, forwardRef } from 'react'

interface SliderProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label?: string
  showValue?: boolean
  valueFormatter?: (value: number) => string
}

export const Slider = forwardRef<HTMLInputElement, SliderProps>(
  ({ 
    label, 
    showValue = true, 
    valueFormatter,
    className = '', 
    value,
    min = 0,
    max = 100,
    ...props 
  }, ref) => {
    const numValue = typeof value === 'string' ? parseFloat(value) : (value as number) || 0
    const numMin = typeof min === 'string' ? parseFloat(min) : min
    const numMax = typeof max === 'string' ? parseFloat(max) : max
    const percentage = ((numValue - numMin) / (numMax - numMin)) * 100

    const displayValue = valueFormatter 
      ? valueFormatter(numValue) 
      : numValue.toString()

    return (
      <div className={`space-y-2 ${className}`}>
        {(label || showValue) && (
          <div className="flex justify-between items-center">
            {label && (
              <label className="text-caption text-text-secondary">
                {label}
              </label>
            )}
            {showValue && (
              <span className="text-caption text-text-muted font-mono">
                {displayValue}
              </span>
            )}
          </div>
        )}
        <div className="relative">
          <input
            ref={ref}
            type="range"
            value={value}
            min={min}
            max={max}
            className="
              w-full h-2 bg-border rounded-full appearance-none cursor-pointer
              [&::-webkit-slider-thumb]:appearance-none
              [&::-webkit-slider-thumb]:w-4
              [&::-webkit-slider-thumb]:h-4
              [&::-webkit-slider-thumb]:rounded-full
              [&::-webkit-slider-thumb]:bg-accent
              [&::-webkit-slider-thumb]:cursor-pointer
              [&::-webkit-slider-thumb]:transition-transform
              [&::-webkit-slider-thumb]:duration-fast
              [&::-webkit-slider-thumb]:hover:scale-110
              [&::-moz-range-thumb]:w-4
              [&::-moz-range-thumb]:h-4
              [&::-moz-range-thumb]:rounded-full
              [&::-moz-range-thumb]:bg-accent
              [&::-moz-range-thumb]:border-0
              [&::-moz-range-thumb]:cursor-pointer
            "
            style={{
              background: `linear-gradient(to right, #FF4F36 0%, #FF4F36 ${percentage}%, #2A2C2F ${percentage}%, #2A2C2F 100%)`,
            }}
            {...props}
          />
        </div>
      </div>
    )
  }
)

Slider.displayName = 'Slider'

