'use client'

import { useEffect } from 'react'
import { useUserProgress } from '@/contexts/UserProgressContext'
import { CenteredCard } from '@/components/ui/CenteredCard'
import { Button } from '@/components/ui/Button'

export default function UnlockedPage() {
  const { unlockStats } = useUserProgress()

  // Unlock stats on mount
  useEffect(() => {
    unlockStats()
  }, [unlockStats])

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
        <Button href="/evaluate" variant="secondary" size="large" fullWidth>
          Start Another Round
        </Button>
      </div>
    </CenteredCard>
  )
}
