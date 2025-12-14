'use client'

import React, { createContext, useContext, useEffect, useState, useCallback, useMemo } from 'react'
import {
  Politician,
  PreferenceType,
  EvaluationItem,
  EvaluationRequest,
  EvaluationResponse,
  PoliticiansListResponse,
  EnrichmentMetadata,
} from '@/types'
import { useAuthSession } from '@/hooks/useAuthSession'
import { useUserPreferences } from './UserPreferencesContext'

interface EvaluationSessionContextType {
  // Politician data
  currentPolitician: Politician | null
  nextPolitician: Politician | null
  loading: boolean

  // Enrichment status
  enrichmentMeta: EnrichmentMetadata | null

  // Session tracking
  completedCount: number
  sessionGoal: number
  isSessionComplete: boolean

  // Actions
  submitEvaluation: (evaluations: EvaluationItem[]) => Promise<{ sessionComplete: boolean }>
  skipPolitician: () => void
  resetSession: () => void
  loadPoliticians: () => Promise<void>
}

export const EvaluationSessionContext = createContext<EvaluationSessionContextType | undefined>(
  undefined,
)

export function EvaluationSessionProvider({ children }: { children: React.ReactNode }) {
  const { session, isAuthenticated } = useAuthSession()
  const { filters, initialized } = useUserPreferences()

  // Politician state
  const [currentPolitician, setCurrentPolitician] = useState<Politician | null>(null)
  const [nextPolitician, setNextPolitician] = useState<Politician | null>(null)
  const [loading, setLoading] = useState(false)
  const [enrichmentMeta, setEnrichmentMeta] = useState<EnrichmentMetadata | null>(null)

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
    async (limit: number = 1, excludeId?: string): Promise<Politician[]> => {
      if (!session?.accessToken) return []

      const params = new URLSearchParams({
        limit: limit.toString(),
      })
      languageFilters.forEach((qid) => params.append('languages', qid))
      countryFilters.forEach((qid) => params.append('countries', qid))
      if (excludeId) {
        params.append('exclude_ids', excludeId)
      }

      const response = await fetch(`/api/evaluations/politicians?${params.toString()}`)

      if (!response.ok) {
        throw new Error(`Failed to fetch politicians: ${response.statusText}`)
      }

      const data: PoliticiansListResponse = await response.json()
      setEnrichmentMeta(data.meta)

      // Ensure all properties have key field set (key = id for backend properties)
      return data.politicians.map((politician) => ({
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

  // Auto-poll when no politicians available but more can be enriched
  useEffect(() => {
    if (currentPolitician !== null) return
    if (loading) return
    if (!enrichmentMeta?.has_enrichable_politicians) return

    const pollInterval = setInterval(() => {
      loadPoliticians()
    }, 5000)

    return () => clearInterval(pollInterval)
  }, [currentPolitician, loading, enrichmentMeta?.has_enrichable_politicians, loadPoliticians])

  const advanceToNextPolitician = useCallback(async () => {
    const newCurrent = nextPolitician

    // If no pre-fetched next politician, show loading state while we fetch
    if (!newCurrent) {
      setLoading(true)
      setCurrentPolitician(null)
      try {
        const politicians = await fetchPoliticians(2, currentPolitician?.id)
        if (politicians.length > 0) {
          setCurrentPolitician(politicians[0])
          setNextPolitician(politicians[1] || null)
        }
      } catch (err) {
        console.error('Error fetching next politician:', err)
      } finally {
        setLoading(false)
      }
      return
    }

    // Immediately move next to current for instant UI update
    setCurrentPolitician(newCurrent)
    setNextPolitician(null)

    // Fetch new next politician in the background, excluding the one we just set as current
    try {
      const politicians = await fetchPoliticians(1, newCurrent.id)
      if (politicians.length > 0) {
        setNextPolitician(politicians[0])
      }
    } catch (err) {
      console.error('Error fetching next politician:', err)
    }
  }, [nextPolitician, currentPolitician?.id, fetchPoliticians])

  const submitEvaluation = useCallback(
    async (evaluations: EvaluationItem[]): Promise<{ sessionComplete: boolean }> => {
      if (isSubmitting) return { sessionComplete: false }

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
          return { sessionComplete: false }
        }

        // Increment session count (this politician counts as reviewed)
        const newCount = completedCount + 1
        const sessionComplete = newCount >= sessionGoal
        setCompletedCount(Math.min(newCount, sessionGoal))

        // Only advance if session isn't complete - avoids flash before redirect
        if (!sessionComplete) {
          await advanceToNextPolitician()
        }

        return { sessionComplete }
      } catch (error) {
        console.error('Error submitting evaluations:', error)
        alert('Error submitting evaluations. Please try again.')
        return { sessionComplete: false }
      } finally {
        setIsSubmitting(false)
      }
    },
    [isSubmitting, completedCount, sessionGoal, advanceToNextPolitician],
  )

  const skipPolitician = useCallback(async () => {
    // Skip without submitting - doesn't count toward session
    await advanceToNextPolitician()
  }, [advanceToNextPolitician])

  const resetSession = useCallback(() => {
    setCompletedCount(0)
  }, [])

  const value: EvaluationSessionContextType = {
    currentPolitician,
    nextPolitician,
    loading,
    enrichmentMeta,
    completedCount,
    sessionGoal,
    isSessionComplete,
    submitEvaluation,
    skipPolitician,
    resetSession,
    loadPoliticians,
  }

  return (
    <EvaluationSessionContext.Provider value={value}>{children}</EvaluationSessionContext.Provider>
  )
}

export function useEvaluationSession() {
  const context = useContext(EvaluationSessionContext)
  if (context === undefined) {
    throw new Error('useEvaluationSession must be used within an EvaluationSessionProvider')
  }
  return context
}
