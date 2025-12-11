import { ReactNode } from 'react'

interface BoxProps {
  children: ReactNode
  className?: string
  onHover?: () => void
}

export function Box({ children, className = '', onHover }: BoxProps) {
  return (
    <div
      className={`bg-white rounded-lg shadow-sm border border-gray-200 transition-all hover:shadow-md ${className}`}
      onMouseEnter={onHover}
    >
      {children}
    </div>
  )
}
