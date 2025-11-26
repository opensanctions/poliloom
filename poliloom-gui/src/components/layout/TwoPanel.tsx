import { ReactNode } from 'react'

interface TwoPanelProps {
  left: ReactNode
  right: ReactNode
}

export function TwoPanel({ left, right }: TwoPanelProps) {
  return (
    <div className="grid grid-cols-[46rem_1fr] bg-gray-50 min-h-0">
      <div className="shadow-lg min-h-0">{left}</div>
      <div className="bg-gray-50 border-l border-gray-200 overflow-hidden min-h-0">{right}</div>
    </div>
  )
}
