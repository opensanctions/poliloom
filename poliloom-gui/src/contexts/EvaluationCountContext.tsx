'use client'

import React, { createContext, useContext, useState, useEffect } from 'react'
import { useSession } from 'next-auth/react'

interface EvaluationCountContextType {
  evaluationCount: number | null
}

const EvaluationCountContext = createContext<EvaluationCountContextType | undefined>(undefined)

export function EvaluationCountProvider({ children }: { children: React.ReactNode }) {
  const { status } = useSession()
  const [evaluationCount, setEvaluationCount] = useState<number | null>(null)

  useEffect(() => {
    if (status !== 'authenticated') return

    const fetchEvaluationCount = async () => {
      try {
        const response = await fetch('/api/stats/count')
        if (response.ok) {
          const data = await response.json()
          setEvaluationCount(data.total)
        }
      } catch {
        // Silently fail
      }
    }

    fetchEvaluationCount()
    const interval = setInterval(fetchEvaluationCount, 2000)
    return () => clearInterval(interval)
  }, [status])

  return (
    <EvaluationCountContext.Provider value={{ evaluationCount }}>
      {children}
    </EvaluationCountContext.Provider>
  )
}

export function useEvaluationCount() {
  const context = useContext(EvaluationCountContext)
  if (context === undefined) {
    throw new Error('useEvaluationCount must be used within an EvaluationCountProvider')
  }
  return context
}
