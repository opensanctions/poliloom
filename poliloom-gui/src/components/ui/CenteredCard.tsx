import { ReactNode } from 'react'

interface CenteredCardProps {
  emoji: string
  title: string
  children?: ReactNode
}

export function CenteredCard({ emoji, title, children }: CenteredCardProps) {
  return (
    <div className="flex items-center justify-center min-h-0 flex-1 bg-gray-50 h-full">
      <div className="text-center max-w-md p-8">
        <div className="text-6xl mb-6">{emoji}</div>
        <h1 className="text-3xl font-bold text-gray-900 mb-4">{title}</h1>
        {children && <div className="text-lg text-gray-600">{children}</div>}
      </div>
    </div>
  )
}
