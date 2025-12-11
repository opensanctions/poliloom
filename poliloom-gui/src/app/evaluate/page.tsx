'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Header } from '@/components/layout/Header'
import { PoliticianEvaluation } from '@/components/evaluation/PoliticianEvaluation'
import { useEvaluationSession } from '@/contexts/EvaluationSessionContext'
import { CenteredCard } from '@/components/ui/CenteredCard'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { useTutorial } from '@/contexts/TutorialContext'
import { useUserPreferences } from '@/contexts/UserPreferencesContext'

export default function EvaluatePage() {
  const router = useRouter()
  const { currentPolitician, loading, isSessionComplete, enrichmentMeta } = useEvaluationSession()
  const { completeBasicTutorial, completeAdvancedTutorial } = useTutorial()
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
      router.push('/evaluate/complete')
    }
  }, [isSessionComplete, router])

  // Determine if we're in a loading state (fetching or waiting for enrichment)
  const isWaitingForData =
    loading || (enrichmentMeta?.has_enrichable_politicians !== false && !currentPolitician)

  // All caught up: no politician and nothing left to enrich
  const isAllCaughtUp =
    !currentPolitician && !loading && enrichmentMeta?.has_enrichable_politicians === false

  if (currentPolitician) {
    return (
      <>
        <Header />
        <PoliticianEvaluation key={currentPolitician.id} politician={currentPolitician} />
      </>
    )
  }

  if (isAllCaughtUp) {
    return (
      <>
        <Header />
        <CenteredCard emoji="🎉" title="You're all caught up!">
          <p className="mb-6">
            No more politicians to evaluate for your current filters. Try different filters to
            continue contributing.
          </p>
          <Button href="/" size="large">
            Start New Session
          </Button>
        </CenteredCard>
      </>
    )
  }

  if (isWaitingForData) {
    return (
      <>
        <Header />
        <CenteredCard emoji="🔍" title="Finding politicians...">
          <div className="flex justify-center">
            <Spinner />
          </div>
        </CenteredCard>
      </>
    )
  }

  return (
    <>
      <Header />
      <CenteredCard emoji="🔍" title="Loading...">
        <div className="flex justify-center">
          <Spinner />
        </div>
      </CenteredCard>
    </>
  )
}
