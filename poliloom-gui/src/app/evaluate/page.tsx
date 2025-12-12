'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { PoliticianEvaluation } from '@/components/evaluation/PoliticianEvaluation'
import { useEvaluationSession } from '@/contexts/EvaluationSessionContext'
import { CenteredCard } from '@/components/ui/CenteredCard'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { useUserProgress } from '@/contexts/UserProgressContext'
import { useUserPreferences } from '@/contexts/UserPreferencesContext'

export default function EvaluatePage() {
  const router = useRouter()
  const { currentPolitician, loading, isSessionComplete, enrichmentMeta } = useEvaluationSession()
  const { completeBasicTutorial, completeAdvancedTutorial, statsUnlocked } = useUserProgress()
  const { isAdvancedMode } = useUserPreferences()

  // Mark tutorials complete once on mount
  useEffect(() => {
    completeBasicTutorial()
    if (isAdvancedMode) {
      completeAdvancedTutorial()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Navigate to completion page when session goal is reached
  useEffect(() => {
    if (isSessionComplete) {
      if (statsUnlocked) {
        router.push('/evaluate/complete')
      } else {
        router.push('/evaluate/unlocked')
      }
    }
  }, [isSessionComplete, router, statsUnlocked])

  // Determine if we're in a loading state (fetching or waiting for enrichment)
  const isWaitingForData =
    loading || (enrichmentMeta?.has_enrichable_politicians !== false && !currentPolitician)

  // All caught up: no politician and nothing left to enrich
  const isAllCaughtUp =
    !currentPolitician && !loading && enrichmentMeta?.has_enrichable_politicians === false

  if (currentPolitician) {
    return <PoliticianEvaluation key={currentPolitician.id} politician={currentPolitician} />
  }

  if (isAllCaughtUp) {
    return (
      <CenteredCard emoji="🎉" title="You're all caught up!">
        <p className="mb-8">
          No more politicians to evaluate for your current filters. Try different filters to
          continue contributing.
        </p>
        <Button href="/" size="large" fullWidth>
          Start New Session
        </Button>
      </CenteredCard>
    )
  }

  if (isWaitingForData) {
    return (
      <CenteredCard emoji="🔍" title="Gathering data...">
        <p className="mb-8">Our AI is reading Wikipedia so you don&apos;t have to. Hang tight!</p>
        <div className="flex justify-center">
          <Spinner />
        </div>
      </CenteredCard>
    )
  }

  return (
    <CenteredCard emoji="🔍" title="Loading...">
      <div className="flex justify-center">
        <Spinner />
      </div>
    </CenteredCard>
  )
}
