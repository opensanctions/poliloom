'use client'

import { Button } from '@/components/ui/Button'
import { CenteredCard } from '@/components/ui/CenteredCard'
import { useSession } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import { useState, useEffect } from 'react'

export default function SetupPage() {
  const { data: session, update } = useSession()
  const router = useRouter()
  const [checking, setChecking] = useState(false)

  useEffect(() => {
    if (session?.hasWikidataAccount) {
      router.push('/')
    }
  }, [session?.hasWikidataAccount, router])

  const handleCheckAgain = async () => {
    setChecking(true)
    try {
      await update()
    } finally {
      setChecking(false)
    }
  }

  return (
    <CenteredCard emoji="😮" title="Woaaaah!">
      <p className="mb-6">
        It looks like you never visited Wikidata! Just hop over there once to activate your account
        and you&apos;ll be ready to go.
      </p>
      <div className="flex flex-col gap-3">
        <Button href="https://www.wikidata.org/wiki/Special:CreateAccount" size="large" fullWidth>
          Go to Wikidata
        </Button>
        <Button
          onClick={handleCheckAgain}
          variant="secondary"
          size="large"
          fullWidth
          disabled={checking}
        >
          {checking ? 'Checking...' : 'Check again'}
        </Button>
      </div>
    </CenteredCard>
  )
}
