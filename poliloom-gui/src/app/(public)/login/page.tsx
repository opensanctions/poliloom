'use client'

import { useAuthSession } from '@/hooks/useAuthSession'
import { Button } from '@/components/ui/Button'
import { CenteredCard } from '@/components/ui/CenteredCard'
import { signIn } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import { useEffect } from 'react'

export default function LoginPage() {
  const { status, isAuthenticated } = useAuthSession()
  const router = useRouter()

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      router.push('/')
    }
  }, [isAuthenticated, router])

  const handleSignIn = () => {
    signIn('wikimedia', { callbackUrl: '/' })
  }

  return (
    <CenteredCard emoji="👋" title="Welcome to PoliLoom">
      <p className="mb-8">
        Help weave political data into{' '}
        <a
          href="https://www.wikidata.org/wiki/Wikidata:Introduction"
          target="_blank"
          rel="noopener noreferrer"
          className="text-accent-foreground hover:text-accent-foreground-hover"
        >
          Wikidata
          <svg
            className="inline w-4 h-4 ml-0.5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
            />
          </svg>
        </a>
        . Learn{' '}
        <a
          href="https://everypolitician.org/about/contribute/poliloom/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-accent-foreground hover:text-accent-foreground-hover"
        >
          what PoliLoom is
          <svg
            className="inline w-4 h-4 ml-0.5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
            />
          </svg>
        </a>
        .
      </p>

      {status === 'loading' && (
        <div className="text-foreground-muted">Loading authentication status...</div>
      )}

      {status === 'unauthenticated' && (
        <div className="flex flex-col gap-4">
          <Button onClick={handleSignIn} size="large" fullWidth>
            Sign in with Wikidata
          </Button>
          <Button
            href="https://www.wikidata.org/wiki/Special:CreateAccount"
            variant="secondary"
            size="large"
            fullWidth
          >
            Create account
          </Button>
        </div>
      )}

      {isAuthenticated && <div className="text-foreground-muted">Redirecting...</div>}
    </CenteredCard>
  )
}
