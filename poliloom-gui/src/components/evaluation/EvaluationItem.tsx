import { ReactNode } from 'react'
import { HeaderedBox } from '@/components/ui/HeaderedBox'

interface EvaluationItemProps {
  title: ReactNode
  children: ReactNode
  onHover?: () => void
}

export function EvaluationItem({ title, children, onHover }: EvaluationItemProps) {
  return (
    <HeaderedBox title={title} onHover={onHover}>
      <div className="space-y-3">{children}</div>
    </HeaderedBox>
  )
}
