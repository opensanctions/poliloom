import { ReactNode } from 'react'
import { Box } from './Box'

interface LegendItem {
  color: string
  label: string
}

interface HeaderedBoxProps {
  title: string | ReactNode
  description?: string
  icon?: string
  legend?: LegendItem[]
  children: ReactNode
  onHover?: () => void
}

export function HeaderedBox({
  title,
  description,
  icon,
  legend,
  children,
  onHover,
}: HeaderedBoxProps) {
  return (
    <Box onHover={onHover}>
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-100 bg-gradient-to-r from-gray-50 to-white rounded-t-lg">
        <div className="flex items-center gap-3">
          {icon && <span className="text-2xl">{icon}</span>}
          <div className="flex-1">
            <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
            {(description || legend) && (
              <div className="flex items-center justify-between mt-0.5 text-sm text-gray-600">
                {description && <p>{description}</p>}
                {legend && (
                  <div className="flex items-center gap-4">
                    {legend.map((item) => (
                      <div key={item.label} className="flex items-center gap-1.5">
                        <span className={`w-3 h-3 rounded-sm ${item.color}`} />
                        <span>{item.label}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="px-6 py-5">{children}</div>
    </Box>
  )
}
