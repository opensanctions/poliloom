import { auth } from '@/auth'
import { redirect } from 'next/navigation'

export async function requireAuth() {
  const session = await auth()

  if (!session) {
    redirect('/auth/login')
  }

  return session
}

export async function getAuthToken() {
  const session = await auth()

  if (!session?.accessToken) {
    throw new Error('No access token available')
  }

  return session.accessToken as string
}
