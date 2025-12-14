import { InputHTMLAttributes, forwardRef } from 'react'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  required?: boolean
  error?: string
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, required, error, className = '', disabled, ...props }, ref) => {
    const baseClasses =
      'w-full px-3 py-2 border border-border-strong rounded-md focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent bg-surface text-foreground placeholder:text-foreground-subtle'

    const errorClasses = error ? 'border-danger-subtle focus:ring-danger-subtle' : ''
    const disabledClasses = disabled
      ? 'bg-surface-hover text-foreground-muted cursor-not-allowed opacity-60'
      : ''

    return (
      <div className={className}>
        {label && (
          <label className="block text-sm font-medium text-foreground-secondary mb-2">
            {label}
            {required && <span className="text-danger-subtle"> *</span>}
          </label>
        )}
        <input
          ref={ref}
          disabled={disabled}
          className={`${baseClasses} ${errorClasses} ${disabledClasses}`}
          {...props}
        />
        {error && <p className="mt-1 text-sm text-danger-foreground">{error}</p>}
      </div>
    )
  },
)

Input.displayName = 'Input'
