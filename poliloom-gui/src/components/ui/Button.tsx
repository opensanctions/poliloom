import { AnchorHTMLAttributes, ButtonHTMLAttributes, forwardRef } from 'react'
import Link from 'next/link'

type ButtonSize = 'small' | 'medium' | 'large' | 'xlarge'

type ButtonVariant = 'primary' | 'secondary' | 'success' | 'danger' | 'info'

type CommonProps = {
  size?: ButtonSize
  variant?: ButtonVariant
  active?: boolean
  fullWidth?: boolean
  children: React.ReactNode
}

type ButtonAsButton = CommonProps & {
  href?: never
} & Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'size'>

type ButtonAsLink = CommonProps & {
  href: string
  disabled?: boolean
} & Omit<AnchorHTMLAttributes<HTMLAnchorElement>, 'href' | 'size'>

type ButtonProps = ButtonAsButton | ButtonAsLink

const sizeClasses: Record<ButtonSize, string> = {
  small: 'px-3 py-1.5 text-sm',
  medium: 'px-4 py-2',
  large: 'px-6 py-3',
  xlarge: 'px-8 py-4',
}

const variantClasses: Record<ButtonVariant, { base: string; active: string }> = {
  primary: {
    base: 'bg-accent text-accent-on-solid font-medium hover:bg-accent-hover',
    active: 'bg-accent-hover text-accent-on-solid font-medium',
  },
  secondary: {
    base: 'text-foreground-tertiary font-medium hover:text-foreground-secondary',
    active: 'bg-surface-active text-foreground font-medium',
  },
  success: {
    base: 'bg-success-muted text-success-foreground font-medium hover:bg-success-muted-hover',
    active: 'bg-success text-accent-on-solid font-medium',
  },
  danger: {
    base: 'bg-danger-muted text-danger-foreground font-medium hover:bg-danger-muted-hover',
    active: 'bg-danger text-accent-on-solid font-medium',
  },
  info: {
    base: 'bg-accent-muted text-accent-foreground font-medium hover:bg-accent-muted-hover',
    active: 'bg-accent text-accent-on-solid font-medium hover:bg-accent-hover',
  },
}

function getClassName({
  size = 'medium',
  variant = 'primary',
  active = false,
  fullWidth = false,
  disabled = false,
  className = '',
}: {
  size?: ButtonSize
  variant?: ButtonVariant
  active?: boolean
  fullWidth?: boolean
  disabled?: boolean
  className?: string
}) {
  const sizeClass = sizeClasses[size]
  const variantClass = active ? variantClasses[variant].active : variantClasses[variant].base
  const baseClasses = `inline-flex items-center justify-center rounded-md transition-colors cursor-pointer whitespace-nowrap ${sizeClass} ${variantClass}`
  const disabledClasses = disabled ? 'opacity-50 cursor-not-allowed pointer-events-none' : ''
  const widthClass = fullWidth ? 'w-full' : ''
  return `${baseClasses} ${disabledClasses} ${widthClass} ${className}`.trim()
}

export const Button = forwardRef<HTMLButtonElement | HTMLAnchorElement, ButtonProps>(
  (props, ref) => {
    const {
      size = 'medium',
      variant = 'primary',
      active = false,
      fullWidth = false,
      className = '',
      children,
      ...rest
    } = props

    // Link variant
    if ('href' in props && props.href !== undefined) {
      const { href, disabled, ...linkProps } = rest as Omit<ButtonAsLink, keyof CommonProps>
      const combinedClasses = getClassName({
        size,
        variant,
        active,
        fullWidth,
        disabled,
        className,
      })

      const isExternal = href.startsWith('http://') || href.startsWith('https://')

      if (isExternal) {
        return (
          <a
            ref={ref as React.Ref<HTMLAnchorElement>}
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className={combinedClasses}
            {...linkProps}
          >
            {children}
          </a>
        )
      }

      return (
        <Link
          ref={ref as React.Ref<HTMLAnchorElement>}
          href={href}
          className={combinedClasses}
          {...linkProps}
        >
          {children}
        </Link>
      )
    }

    // Button variant
    const { disabled, ...buttonProps } = rest as Omit<ButtonAsButton, keyof CommonProps>
    const combinedClasses = getClassName({
      size,
      variant,
      active,
      fullWidth,
      disabled,
      className,
    })

    return (
      <button
        ref={ref as React.Ref<HTMLButtonElement>}
        disabled={disabled}
        className={combinedClasses}
        {...buttonProps}
      >
        {children}
      </button>
    )
  },
)

Button.displayName = 'Button'
