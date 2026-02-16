'use client'

import { useAuthSession } from '@/hooks/useAuthSession'
import { Button } from '@/components/ui/Button'
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
    <main className="grid place-items-center py-12 px-4 sm:px-6 lg:px-8 min-h-0 overflow-y-auto">
      <div className="text-center max-w-4xl">
        <h1 className="text-4xl font-bold text-foreground mb-4">Welcome to PoliLoom</h1>
        <p className="text-lg text-foreground-tertiary mb-8">
          Help weave the world&apos;s political data into{' '}
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
          .{' '}
          <a
            href="https://everypolitician.org/about/contribute/poliloom/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent-foreground hover:text-accent-foreground-hover"
          >
            How does it work?
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
        </p>

        {status === 'loading' && (
          <div className="text-foreground-muted">Loading authentication status...</div>
        )}

        {status === 'unauthenticated' && (
          <div className="flex flex-col items-center gap-5">
            <Button onClick={handleSignIn} size="large">
              Sign in with Wikidata
            </Button>
            <Button
              href="https://www.wikidata.org/wiki/Special:CreateAccount"
              variant="secondary"
              size="small"
            >
              Create Wikidata account
            </Button>
          </div>
        )}

        {isAuthenticated && <div className="text-foreground-muted">Redirecting...</div>}
      </div>
    </main>
  )
}
