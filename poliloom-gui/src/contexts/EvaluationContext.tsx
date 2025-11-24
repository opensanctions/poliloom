'use client'

import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  useMemo,
  startTransition,
} from 'react'
import { useRouter } from 'next/navigation'
import {
  Politician,
  PreferenceType,
  EvaluationItem,
  EvaluationRequest,
  EvaluationResponse,
} from '@/types'
import { useAuthSession } from '@/hooks/useAuthSession'
import { useEvaluationFilters } from './EvaluationFiltersContext'

interface EvaluationContextType {
  // Politician data
  currentPolitician: Politician | null
  nextPolitician: Politician | null
  loading: boolean

  // Session tracking
  completedCount: number
  sessionGoal: number
  isSessionComplete: boolean

  // Actions
  submitEvaluation: (evaluations: EvaluationItem[]) => Promise<void>
  skipPolitician: () => void
  resetSession: () => void
  loadPoliticians: () => Promise<void>
}

const EvaluationContext = createContext<EvaluationContextType | undefined>(undefined)

export function EvaluationProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const { session, isAuthenticated } = useAuthSession()
  const { filters, initialized } = useEvaluationFilters()

  // Politician state
  const [currentPolitician, setCurrentPolitician] = useState<Politician | null>(null)
  const [nextPolitician, setNextPolitician] = useState<Politician | null>(null)
  const [loading, setLoading] = useState(false)

  // Session state
  const sessionGoal = 5
  const [completedCount, setCompletedCount] = useState(0)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const isSessionComplete = completedCount >= sessionGoal

  // Memoize filter arrays to prevent unnecessary recreations
  const languageFilters = useMemo(
    () =>
      filters
        .filter((p) => p.preference_type === PreferenceType.LANGUAGE)
        .map((p) => p.wikidata_id),
    [filters],
  )

  const countryFilters = useMemo(
    () =>
      filters.filter((p) => p.preference_type === PreferenceType.COUNTRY).map((p) => p.wikidata_id),
    [filters],
  )

  const fetchPoliticians = useCallback(
    async (limit: number = 1): Promise<Politician[]> => {
      if (!session?.accessToken) return []

      const params = new URLSearchParams({
        limit: limit.toString(),
        has_unevaluated: 'true',
      })
      languageFilters.forEach((qid) => params.append('languages', qid))
      countryFilters.forEach((qid) => params.append('countries', qid))

      const response = await fetch(`/api/politicians?${params.toString()}`)

      if (!response.ok) {
        throw new Error(`Failed to fetch politicians: ${response.statusText}`)
      }

      const politicians: Politician[] = await response.json()

      // Ensure all properties have key field set (key = id for backend properties)
      return politicians.map((politician) => ({
        ...politician,
        properties: politician.properties.map((prop) => ({
          ...prop,
          key: prop.id || prop.key,
        })),
      }))
    },
    [session?.accessToken, languageFilters, countryFilters],
  )

  // Clear politicians when filters change
  useEffect(() => {
    setCurrentPolitician(null)
    setNextPolitician(null)
  }, [languageFilters, countryFilters])

  const loadPoliticians = useCallback(async () => {
    if (!isAuthenticated || !initialized) return

    setLoading(true)
    try {
      const politicians = await fetchPoliticians(2)

      if (politicians.length > 0) {
        setCurrentPolitician(politicians[0])
        setNextPolitician(politicians[1] || null)
      }
    } catch (err) {
      console.error('Error fetching politicians:', err)
    } finally {
      setLoading(false)
    }
  }, [isAuthenticated, initialized, fetchPoliticians])

  // Fetch politicians when current is null
  useEffect(() => {
    if (!isAuthenticated || !initialized || loading) return
    if (currentPolitician !== null) return

    loadPoliticians()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated, initialized, currentPolitician, loadPoliticians])

  const advanceToNextPolitician = useCallback(async () => {
    // Immediately move next to current for instant UI update
    setCurrentPolitician(nextPolitician)
    setNextPolitician(null)

    // Fetch new next politician in the background
    try {
      const politicians = await fetchPoliticians(1)
      if (politicians.length > 0) {
        setNextPolitician(politicians[0])
      }
    } catch (err) {
      console.error('Error fetching next politician:', err)
    }
  }, [nextPolitician, fetchPoliticians])

  const submitEvaluation = useCallback(
    async (evaluations: EvaluationItem[]) => {
      if (isSubmitting) return

      setIsSubmitting(true)
      try {
        const evaluationData: EvaluationRequest = { evaluations }

        const response = await fetch('/api/evaluations', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(evaluationData),
        })

        if (!response.ok) {
          throw new Error(`Failed to submit evaluations: ${response.statusText}`)
        }

        const result: EvaluationResponse = await response.json()
        if (!result.success) {
          console.error('Evaluation errors:', result.errors)
          alert(`Error submitting evaluations: ${result.message}`)
          return
        }

        // Increment session count (this politician counts as reviewed)
        setCompletedCount((prev) => Math.min(prev + 1, sessionGoal))

        // Check if we just completed the session
        const newCount = completedCount + 1
        if (newCount >= sessionGoal) {
          // Session complete - navigate to completion page
          router.push('/evaluate/complete')
          // Advance to next politician as low-priority transition to avoid flash before navigation
          startTransition(() => {
            advanceToNextPolitician()
          })
        } else {
          // Normal flow: move to next politician
          await advanceToNextPolitician()
        }
      } catch (error) {
        console.error('Error submitting evaluations:', error)
        alert('Error submitting evaluations. Please try again.')
      } finally {
        setIsSubmitting(false)
      }
    },
    [isSubmitting, completedCount, sessionGoal, router, advanceToNextPolitician],
  )

  const skipPolitician = useCallback(async () => {
    // Skip without submitting - doesn't count toward session
    await advanceToNextPolitician()
  }, [advanceToNextPolitician])

  const resetSession = useCallback(() => {
    setCompletedCount(0)
  }, [])

  const value: EvaluationContextType = {
    currentPolitician,
    nextPolitician,
    loading,
    completedCount,
    sessionGoal,
    isSessionComplete,
    submitEvaluation,
    skipPolitician,
    resetSession,
    loadPoliticians,
  }

  return <EvaluationContext.Provider value={value}>{children}</EvaluationContext.Provider>
}

export function useEvaluation() {
  const context = useContext(EvaluationContext)
  if (context === undefined) {
    throw new Error('useEvaluation must be used within an EvaluationProvider')
  }
  return context
}
