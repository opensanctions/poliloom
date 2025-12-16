import { ReactNode } from 'react'

interface TwoPanelProps {
  left: ReactNode
  right: ReactNode
}

export function TwoPanel({ left, right }: TwoPanelProps) {
  return (
    <div className="grid grid-cols-[min(50vw,46rem)_1fr] min-h-0">
      <div className="shadow-lg min-h-0">{left}</div>
      <div className="border-l border-border overflow-hidden min-h-0">{right}</div>
    </div>
  )
}
