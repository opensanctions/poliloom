'use client'

import { useSession, signOut } from 'next-auth/react'
import Link from 'next/link'
import { handleSignIn } from '@/lib/actions'
import { Button } from './Button'

export function Header() {
  const { data: session, status } = useSession()

  return (
    <header className="bg-white shadow-sm border-b sticky top-0 z-10">
      <div className="w-full pl-6 pr-4 sm:pr-6 lg:pr-8">
        <div className="flex justify-between items-center h-16">
          <div className="flex items-center">
            <Link href="/" className="text-xl font-bold text-gray-900">
              PoliLoom
            </Link>
          </div>

          <div className="flex items-center space-x-4">
            {status === 'loading' && <div className="text-sm text-gray-500">Loading...</div>}

            {status === 'authenticated' && session?.user && (
              <>
                <div className="text-sm text-gray-700">
                  Welcome, {session.user.name || session.user.email}
                </div>
                <Button
                  href="/preferences"
                  variant="ghost"
                  size="sm"
                  className="text-gray-600 hover:text-gray-800"
                >
                  Preferences
                </Button>
                <Button
                  onClick={() => signOut({ callbackUrl: '/' })}
                  variant="ghost"
                  size="sm"
                  className="text-gray-500 hover:text-gray-700"
                >
                  Sign out
                </Button>
              </>
            )}

            {status === 'unauthenticated' && (
              <form action={handleSignIn}>
                <Button
                  type="submit"
                  variant="ghost"
                  size="sm"
                  className="text-indigo-600 hover:text-indigo-500"
                >
                  Sign in
                </Button>
              </form>
            )}
          </div>
        </div>
      </div>
    </header>
  )
}
