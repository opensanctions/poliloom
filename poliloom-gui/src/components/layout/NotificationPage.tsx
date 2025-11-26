'use client'

import { ReactNode } from 'react'
import { Header } from './Header'
import { CenteredCard } from '@/components/ui/CenteredCard'

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
      <CenteredCard emoji={emoji} title={title}>
        {description && <div className="mb-8">{description}</div>}
        {children && <div className="flex flex-col gap-4">{children}</div>}
      </CenteredCard>
    </>
  )
}
