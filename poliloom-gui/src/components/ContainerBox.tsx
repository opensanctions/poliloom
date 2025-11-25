import { ReactNode } from 'react'
import { Spinner } from './Spinner'

interface ContainerBoxProps {
  title: string | ReactNode
  description?: string
  icon?: string
  loading?: boolean
  children: ReactNode
  onHover?: () => void
}

export function ContainerBox({
  title,
  description,
  icon,
  loading = false,
  children,
  onHover,
}: ContainerBoxProps) {
  return (
    <div
      className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden transition-all hover:shadow-md"
      onMouseEnter={onHover}
    >
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-100 bg-gradient-to-r from-gray-50 to-white">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            {icon && <span className="text-2xl">{icon}</span>}
            <div>
              <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
              {description && <p className="text-sm text-gray-600 mt-0.5">{description}</p>}
            </div>
          </div>
          {loading && (
            <div className="ml-4">
              <Spinner />
            </div>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="px-6 py-5">{children}</div>
    </div>
  )
}
