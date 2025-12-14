import { InputHTMLAttributes, forwardRef } from 'react'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  required?: boolean
  error?: string
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, required, error, className = '', disabled, ...props }, ref) => {
    const baseClasses =
      'w-full px-3 py-2 border border-border-strong rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent bg-surface text-foreground placeholder:text-foreground-subtle'

    const errorClasses = error ? 'border-red-500 focus:ring-red-500' : ''
    const disabledClasses = disabled
      ? 'bg-surface-hover text-foreground-muted cursor-not-allowed opacity-60'
      : ''

    return (
      <div className={className}>
        {label && (
          <label className="block text-sm font-medium text-foreground-secondary mb-2">
            {label}
            {required && <span className="text-red-500"> *</span>}
          </label>
        )}
        <input
          ref={ref}
          disabled={disabled}
          className={`${baseClasses} ${errorClasses} ${disabledClasses}`}
          {...props}
        />
        {error && <p className="mt-1 text-sm text-red-600">{error}</p>}
      </div>
    )
  },
)

Input.displayName = 'Input'
