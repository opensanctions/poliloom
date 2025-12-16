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
          Help build the world&apos;s largest open database of politicians.
        </p>

        {status === 'loading' && (
          <div className="text-foreground-muted">Loading authentication status...</div>
        )}

        {status === 'unauthenticated' && (
          <Button onClick={handleSignIn} size="large">
            Sign in with MediaWiki
          </Button>
        )}

        {isAuthenticated && <div className="text-foreground-muted">Redirecting...</div>}
      </div>
    </main>
  )
}
