'use client'

import { useEffect } from 'react'
import { useUserProgress } from '@/contexts/UserProgressContext'
import { useEvaluationSession } from '@/contexts/EvaluationSessionContext'
import { useNextPoliticianContext } from '@/contexts/NextPoliticianContext'
import { CenteredCard } from '@/components/ui/CenteredCard'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'

export default function UnlockedPage() {
  const { unlockStats } = useUserProgress()
  const { endSession, startSession } = useEvaluationSession()
  const { nextHref, loading } = useNextPoliticianContext()

  useEffect(() => {
    unlockStats()
    endSession()
  }, [unlockStats, endSession])

  return (
    <CenteredCard emoji="🎉" title="Stats Unlocked!">
      <p className="mb-8">
        Amazing work, you&apos;ve completed your first session. You can now access the community
        stats.
      </p>
      <div className="flex flex-col gap-4">
        <Button href="/stats" size="large" fullWidth>
          View Stats
        </Button>
        {loading ? (
          <div className="flex justify-center">
            <Spinner />
          </div>
        ) : nextHref ? (
          <Button
            href={nextHref}
            variant="secondary"
            size="large"
            fullWidth
            onClick={() => startSession()}
          >
            Start Another Round
          </Button>
        ) : (
          <Button href="/" variant="secondary" size="large" fullWidth>
            Start Another Round
          </Button>
        )}
      </div>
    </CenteredCard>
  )
}
