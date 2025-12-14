import { InputHTMLAttributes, forwardRef } from 'react'

type ToggleProps = {
  checked?: boolean
  onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void
} & Omit<InputHTMLAttributes<HTMLInputElement>, 'type' | 'size'>

export const Toggle = forwardRef<HTMLInputElement, ToggleProps>(
  ({ checked, onChange, className = '', ...props }, ref) => {
    return (
      <span className={`relative inline-block w-11 h-6 shrink-0 ${className}`}>
        <input
          ref={ref}
          type="checkbox"
          role="switch"
          aria-checked={checked}
          checked={checked}
          onChange={onChange}
          className="sr-only peer"
          {...props}
        />
        <span
          aria-hidden="true"
          className="
            absolute inset-0 rounded-full bg-border-strong cursor-pointer
            transition-colors duration-200 ease-in-out
            peer-checked:bg-indigo-600
            peer-focus-visible:ring-2 peer-focus-visible:ring-indigo-500 peer-focus-visible:ring-offset-2
          "
        />
        <span
          aria-hidden="true"
          className="
            absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white shadow-sm pointer-events-none
            transition-transform duration-200 ease-in-out
            peer-checked:translate-x-5
          "
        />
      </span>
    )
  },
)

Toggle.displayName = 'Toggle'
