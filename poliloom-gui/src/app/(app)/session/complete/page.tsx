'use client'

import { useEffect } from 'react'
import { useEvaluationSession } from '@/contexts/EvaluationSessionContext'
import { useNextPoliticianContext } from '@/contexts/NextPoliticianContext'
import { CenteredCard } from '@/components/ui/CenteredCard'
import { Button } from '@/components/ui/Button'

export default function CompletePage() {
  const { sessionGoal, endSession, startSession } = useEvaluationSession()
  const { nextHref, politicianReady, loading } = useNextPoliticianContext()

  useEffect(() => {
    endSession()
  }, [endSession])

  return (
    <CenteredCard emoji="🎉" title="Session Complete!">
      <p className="mb-8">Great work! You&apos;ve reviewed {sessionGoal} politicians.</p>
      <div className="flex flex-col gap-4">
        <Button
          href={nextHref}
          disabled={loading}
          size="large"
          fullWidth
          onClick={politicianReady ? () => startSession() : undefined}
        >
          Start Another Round
        </Button>
        <Button href="/" variant="secondary" size="large" fullWidth>
          Return Home
        </Button>
      </div>
    </CenteredCard>
  )
}
