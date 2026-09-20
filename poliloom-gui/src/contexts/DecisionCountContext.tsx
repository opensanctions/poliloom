'use client'

import React, { createContext, useContext, useState } from 'react'
import { useEventStream } from '@/contexts/EventStreamContext'

interface DecisionCountContextType {
  decisionCount: number | null
}

const DecisionCountContext = createContext<DecisionCountContextType | undefined>(undefined)

export function DecisionCountProvider({
  initialCount,
  children,
}: {
  initialCount: number | null
  children: React.ReactNode
}) {
  const [decisionCount, setDecisionCount] = useState<number | null>(initialCount)

  useEventStream(
    'decision_count',
    (event) => {
      setDecisionCount(event.total)
    },
    [],
  )

  return (
    <DecisionCountContext.Provider value={{ decisionCount }}>
      {children}
    </DecisionCountContext.Provider>
  )
}

export function useDecisionCount() {
  const context = useContext(DecisionCountContext)
  if (context === undefined) {
    throw new Error('useDecisionCount must be used within a DecisionCountProvider')
  }
  return context
}
