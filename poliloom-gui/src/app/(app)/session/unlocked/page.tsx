'use client'

import { useEffect } from 'react'
import { useUser } from '@/contexts/UserContext'
import { useEvaluationSession } from '@/contexts/EvaluationSessionContext'
import { useNextPoliticianContext } from '@/contexts/NextPoliticianContext'
import { CenteredCard } from '@/components/ui/CenteredCard'
import { Button } from '@/components/ui/Button'

export default function UnlockedPage() {
  const { patch } = useUser()
  const { endSession, startSession } = useEvaluationSession()
  const { nextHref, politicianReady, loading } = useNextPoliticianContext()

  useEffect(() => {
    patch({ settings: { stats_unlocked: true } })
    endSession()
  }, [patch, endSession])

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
        <Button
          href={nextHref}
          disabled={loading}
          variant="secondary"
          size="large"
          fullWidth
          onClick={politicianReady ? () => startSession() : undefined}
        >
          Start Another Round
        </Button>
      </div>
    </CenteredCard>
  )
}
