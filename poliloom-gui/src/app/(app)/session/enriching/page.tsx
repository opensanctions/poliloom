'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useNextPoliticianContext } from '@/contexts/NextPoliticianContext'
import { CenteredCard } from '@/components/ui/CenteredCard'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'

export default function EnrichingPage() {
  const router = useRouter()
  const { nextHref, enrichmentMeta, loading } = useNextPoliticianContext()

  // Auto-navigate when a politician becomes available
  useEffect(() => {
    if (nextHref) {
      router.push(nextHref)
    }
  }, [nextHref, router])

  const isAllCaughtUp =
    !nextHref && !loading && enrichmentMeta?.has_enrichable_politicians === false

  if (isAllCaughtUp) {
    return (
      <CenteredCard emoji="✅" title="All Caught Up!">
        <p className="mb-8">
          There are no more politicians to evaluate for your current filters. Try adjusting your
          filters to continue contributing.
        </p>
        <Button href="/" size="large" fullWidth>
          Return Home
        </Button>
      </CenteredCard>
    )
  }

  return (
    <CenteredCard emoji="🔍" title="Gathering Data...">
      <p className="mb-8">
        Our AI is reading Wikipedia so you don&apos;t have to. A new politician will appear
        automatically once the data is ready.
      </p>
      <div className="flex justify-center">
        <Spinner />
      </div>
    </CenteredCard>
  )
}
