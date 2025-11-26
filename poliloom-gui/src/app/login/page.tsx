'use client'

import { useAuthSession } from '@/hooks/useAuthSession'
import { Header } from '@/components/layout/Header'
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
    <>
      <Header />
      <main className="bg-gray-50 grid place-items-center py-12 px-4 sm:px-6 lg:px-8 min-h-0 overflow-y-auto">
        <div className="text-center max-w-4xl">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">Contribute to Open Knowledge</h1>
          <p className="text-lg text-gray-600 mb-8">
            Help verify politician information. Your reviews ensure accurate, reliable data is
            available to everyone.
          </p>

          {status === 'loading' && (
            <div className="text-gray-500">Loading authentication status...</div>
          )}

          {status === 'unauthenticated' && (
            <div className="space-y-4">
              <p className="text-gray-600">
                Please sign in with your MediaWiki account to start evaluating data.
              </p>
              <Button onClick={handleSignIn} size="large">
                Sign in with MediaWiki
              </Button>
            </div>
          )}

          {isAuthenticated && <div className="text-gray-500">Redirecting...</div>}
        </div>
      </main>
    </>
  )
}
