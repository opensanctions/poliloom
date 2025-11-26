import { ReactNode } from 'react'
import { ContainerBox } from '@/components/ui/ContainerBox'

interface EvaluationItemProps {
  title: ReactNode
  children: ReactNode
  onHover?: () => void
}

export function EvaluationItem({ title, children, onHover }: EvaluationItemProps) {
  return (
    <ContainerBox title={title} onHover={onHover}>
      <div className="space-y-3">{children}</div>
    </ContainerBox>
  )
}
