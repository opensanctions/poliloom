'use client'

import { useRouter } from 'next/navigation'
import { useEvaluationSession } from '@/contexts/EvaluationSessionContext'
import { CenteredCard } from '@/components/ui/CenteredCard'
import { Button } from '@/components/ui/Button'

export default function CompletePage() {
  const router = useRouter()
  const { sessionGoal, resetSession } = useEvaluationSession()

  const handleStartAnother = () => {
    resetSession()
    router.push('/evaluate')
  }

  const handleReturnHome = () => {
    resetSession()
    router.push('/')
  }

  return (
    <CenteredCard emoji="🎉" title="Session Complete!">
      <p className="mb-8">Great work! You&apos;ve reviewed {sessionGoal} politicians.</p>
      <div className="flex flex-col gap-4">
        <Button onClick={handleStartAnother} size="large" fullWidth>
          Start Another Round
        </Button>
        <Button onClick={handleReturnHome} variant="secondary" size="large" fullWidth>
          Return Home
        </Button>
      </div>
    </CenteredCard>
  )
}
