'use client'

import { useEffect } from 'react'
import { useEvaluationSession } from '@/contexts/EvaluationSessionContext'
import { CenteredCard } from '@/components/ui/CenteredCard'
import { Button } from '@/components/ui/Button'

export default function CompletePage() {
  const { sessionGoal, resetSession } = useEvaluationSession()

  // Reset session on mount so navigating away (e.g., via logo) starts fresh
  useEffect(() => {
    resetSession()
  }, [resetSession])

  return (
    <CenteredCard emoji="🎉" title="Session Complete!">
      <p className="mb-8">Great work! You&apos;ve reviewed {sessionGoal} politicians.</p>
      <div className="flex flex-col gap-4">
        <Button href="/evaluate" size="large" fullWidth>
          Start Another Round
        </Button>
        <Button href="/" variant="secondary" size="large" fullWidth>
          Return Home
        </Button>
      </div>
    </CenteredCard>
  )
}
