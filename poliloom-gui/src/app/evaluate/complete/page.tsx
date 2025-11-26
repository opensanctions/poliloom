'use client'

import { useRouter } from 'next/navigation'
import { useEvaluationSession } from '@/contexts/EvaluationSessionContext'
import { NotificationPage } from '@/components/layout/NotificationPage'
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
    <NotificationPage
      emoji="🎉"
      title="Session Complete!"
      description={<p>Great work! You&apos;ve reviewed {sessionGoal} politicians.</p>}
    >
      <Button onClick={handleStartAnother} size="large" fullWidth>
        Start Another Round
      </Button>
      <Button onClick={handleReturnHome} variant="secondary" size="large" fullWidth>
        Return Home
      </Button>
    </NotificationPage>
  )
}
