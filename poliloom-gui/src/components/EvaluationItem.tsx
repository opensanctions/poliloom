import { ReactNode } from 'react'
import { ContainerBox } from './ContainerBox'

interface EvaluationItemProps {
  title: ReactNode
  children: ReactNode
  onHover?: () => void
  hasNewData?: boolean
}

export function EvaluationItem({ title, children, onHover, hasNewData }: EvaluationItemProps) {
  return (
    <ContainerBox title={title} onHover={onHover} hasNewData={hasNewData}>
      <div className="space-y-3">{children}</div>
    </ContainerBox>
  )
}
