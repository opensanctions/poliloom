import { useSession, signOut } from 'next-auth/react'
import { useEffect } from 'react'

export function useAuthSession() {
  const { data: session, status } = useSession()

  useEffect(() => {
    if (session?.error === 'RefreshAccessTokenError') {
      // Redirect to login page when refresh token is expired or missing
      signOut({ callbackUrl: '/login' })
    }
  }, [session])

  return {
    session,
    status,
    isAuthenticated: status === 'authenticated' && !session?.error,
  }
}
