import { ReactNode } from 'react'
import { Box } from './Box'

interface HeaderedBoxProps {
  title: string | ReactNode
  description?: string
  icon?: string
  children: ReactNode
  onHover?: () => void
}

export function HeaderedBox({ title, description, icon, children, onHover }: HeaderedBoxProps) {
  return (
    <Box onHover={onHover}>
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-100 bg-gradient-to-r from-gray-50 to-white">
        <div className="flex items-center gap-3">
          {icon && <span className="text-2xl">{icon}</span>}
          <div>
            <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
            {description && <p className="text-sm text-gray-600 mt-0.5">{description}</p>}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="px-6 py-5">{children}</div>
    </Box>
  )
}
