'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useEvaluationSession } from '@/contexts/EvaluationSessionContext'
import { useUserProgress } from '@/contexts/UserProgressContext'
import { CenteredCard } from '@/components/ui/CenteredCard'
import { Button } from '@/components/ui/Button'

export default function UnlockedPage() {
  const router = useRouter()
  const { resetSession } = useEvaluationSession()
  const { unlockStats } = useUserProgress()

  useEffect(() => {
    unlockStats()
  }, [unlockStats])

  const handleViewStats = () => {
    resetSession()
    router.push('/stats')
  }

  const handleStartAnother = () => {
    resetSession()
    router.push('/evaluate')
  }

  return (
    <CenteredCard emoji="🔓" title="Stats Unlocked!">
      <p className="mb-8">
        Great work! You&apos;ve completed your first session and unlocked the community stats page.
      </p>
      <div className="flex flex-col gap-4">
        <Button onClick={handleViewStats} size="large" fullWidth>
          View Stats
        </Button>
        <Button onClick={handleStartAnother} variant="secondary" size="large" fullWidth>
          Start Another Round
        </Button>
      </div>
    </CenteredCard>
  )
}
