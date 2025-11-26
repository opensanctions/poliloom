import { InputHTMLAttributes, forwardRef } from 'react'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  required?: boolean
  error?: string
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, required, error, className = '', disabled, ...props }, ref) => {
    const baseClasses =
      'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-gray-900 placeholder:text-gray-400'

    const errorClasses = error ? 'border-red-500 focus:ring-red-500' : ''
    const disabledClasses = disabled
      ? 'bg-gray-100 text-gray-500 cursor-not-allowed opacity-60'
      : ''

    return (
      <div className={className}>
        {label && (
          <label className="block text-sm font-medium text-gray-700 mb-2">
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
