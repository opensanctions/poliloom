'use client'

import { useSession, signOut, signIn } from 'next-auth/react'
import { Button } from '@/components/ui/Button'

export function AuthButton() {
  const { status } = useSession()

  if (status === 'authenticated') {
    return (
      <Button
        onClick={() => signOut({ callbackUrl: '/login' })}
        variant="secondary"
        size="small"
        className="max-md:text-lg max-md:py-4 max-md:px-6 max-md:justify-start"
      >
        Sign out
      </Button>
    )
  }

  if (status === 'unauthenticated') {
    return (
      <Button
        onClick={() => signIn('wikimedia', { callbackUrl: '/' })}
        variant="secondary"
        size="small"
        className="max-md:text-lg max-md:py-4 max-md:px-6 max-md:justify-start"
      >
        Sign in
      </Button>
    )
  }

  return null
}
