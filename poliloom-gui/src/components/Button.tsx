import { ButtonHTMLAttributes, forwardRef } from 'react'
import Link from 'next/link'

type ButtonSize = 'sm' | 'md'

type ButtonVariant = 'primary' | 'secondary' | 'success' | 'danger' | 'info' | 'ghost'

interface BaseButtonProps {
  size?: ButtonSize
  variant?: ButtonVariant
  active?: boolean
  fullWidth?: boolean
  disabled?: boolean
  children: React.ReactNode
}

type ButtonAsButton = BaseButtonProps &
  Omit<ButtonHTMLAttributes<HTMLButtonElement>, keyof BaseButtonProps> & {
    href?: never
  }

type ButtonAsLink = BaseButtonProps &
  Omit<React.ComponentPropsWithoutRef<typeof Link>, keyof BaseButtonProps> & {
    href: string
  }

type ButtonProps = ButtonAsButton | ButtonAsLink

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'px-2 py-1 text-sm',
  md: 'px-4 py-2',
}

const variantClasses: Record<ButtonVariant, { base: string; active: string }> = {
  primary: {
    base: 'bg-indigo-600 text-white font-medium hover:bg-indigo-700',
    active: 'bg-indigo-700 text-white font-medium',
  },
  secondary: {
    base: 'text-gray-700 font-medium hover:bg-gray-100',
    active: 'bg-gray-200 text-gray-900 font-medium',
  },
  success: {
    base: 'bg-green-100 text-green-700 font-medium hover:bg-green-200',
    active: 'bg-green-600 text-white font-medium',
  },
  danger: {
    base: 'bg-red-100 text-red-700 font-medium hover:bg-red-200',
    active: 'bg-red-600 text-white font-medium',
  },
  info: {
    base: 'bg-blue-100 text-blue-700 font-medium hover:bg-blue-200',
    active: 'bg-blue-700 text-white font-medium hover:bg-blue-800',
  },
  ghost: {
    base: 'text-gray-600 hover:text-gray-800 transition-colors font-medium',
    active: 'text-gray-900 font-medium',
  },
}

export const Button = forwardRef<HTMLButtonElement | HTMLAnchorElement, ButtonProps>(
  (
    {
      size = 'md',
      variant = 'primary',
      active = false,
      fullWidth = false,
      className = '',
      children,
      disabled,
      ...props
    },
    ref,
  ) => {
    const sizeClass = sizeClasses[size]
    const variantClass = active ? variantClasses[variant].active : variantClasses[variant].base

    const baseClasses = `inline-flex items-center justify-center rounded-md transition-colors cursor-pointer ${sizeClass} ${variantClass}`
    const disabledClasses = disabled ? 'opacity-50 cursor-not-allowed' : ''
    const widthClass = fullWidth ? 'w-full' : ''
    const combinedClasses = `${baseClasses} ${disabledClasses} ${widthClass} ${className}`.trim()

    if ('href' in props && props.href) {
      return (
        <Link
          ref={ref as React.Ref<HTMLAnchorElement>}
          {...(props as React.ComponentPropsWithoutRef<typeof Link>)}
          className={combinedClasses}
          aria-disabled={disabled}
        >
          {children}
        </Link>
      )
    }

    return (
      <button
        ref={ref as React.Ref<HTMLButtonElement>}
        {...(props as ButtonHTMLAttributes<HTMLButtonElement>)}
        disabled={disabled}
        className={combinedClasses}
      >
        {children}
      </button>
    )
  },
)

Button.displayName = 'Button'
