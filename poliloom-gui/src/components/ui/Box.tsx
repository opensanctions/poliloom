import { ReactNode } from 'react'

interface BoxProps {
  children: ReactNode
  className?: string
  onHover?: () => void
}

export function Box({ children, className = '', onHover }: BoxProps) {
  return (
    <div
      className={`bg-surface rounded-lg shadow-sm border border-border transition-all hover:shadow-md ${className}`}
      onMouseEnter={onHover}
    >
      {children}
    </div>
  )
}
