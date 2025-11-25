'use client'

import { ReactNode } from 'react'
import { Header } from './Header'

interface NotificationPageProps {
  emoji: string
  title: string
  description?: ReactNode
  children?: ReactNode
  showHeader?: boolean
}

export function NotificationPage({
  emoji,
  title,
  description,
  children,
  showHeader = true,
}: NotificationPageProps) {
  return (
    <>
      {showHeader && <Header />}
      <div className="flex items-center justify-center min-h-0 flex-1 bg-gray-50">
        <div className="text-center max-w-md p-8">
          <div className="text-6xl mb-6">{emoji}</div>
          <h1 className="text-3xl font-bold text-gray-900 mb-4">{title}</h1>
          {description && <div className="text-lg text-gray-600 mb-8">{description}</div>}
          {children && <div className="flex flex-col gap-4">{children}</div>}
        </div>
      </div>
    </>
  )
}
