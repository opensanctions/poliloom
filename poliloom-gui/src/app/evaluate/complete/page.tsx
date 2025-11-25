'use client'

import { useRouter } from 'next/navigation'
import { useEvaluation } from '@/contexts/EvaluationContext'
import { NotificationPage } from '@/components/NotificationPage'
import { Button } from '@/components/Button'

export default function CompletePage() {
  const router = useRouter()
  const { sessionGoal, resetSession } = useEvaluation()

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
      <Button onClick={handleStartAnother} className="px-6 py-3 w-full">
        Start Another Round
      </Button>
      <Button onClick={handleReturnHome} variant="secondary" className="px-6 py-3 w-full">
        Return Home
      </Button>
    </NotificationPage>
  )
}
