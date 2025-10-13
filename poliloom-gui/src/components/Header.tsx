'use client'

import { useSession, signOut, signIn } from 'next-auth/react'
import { Button } from './Button'
import { Anchor } from './Anchor'

export function Header() {
  const { data: session, status } = useSession()

  return (
    <header className="bg-white shadow-sm border-b sticky top-0 z-10">
      <div className="w-full pl-6 pr-4 sm:pr-6 lg:pr-8">
        <div className="flex justify-between items-center h-16">
          <div className="flex items-center">
            <Anchor href="/" className="flex items-center gap-2 text-xl font-bold text-gray-900">
              <img
                src="https://assets.opensanctions.org/images/ep/logo-icon-color.svg"
                alt="European Parliament"
                className="h-8 w-8"
              />
              PoliLoom
            </Anchor>
          </div>

          <div className="flex items-center space-x-4">
            {status === 'loading' && <div className="text-sm text-gray-500">Loading...</div>}

            {status === 'authenticated' && session?.user && (
              <>
                <div className="text-sm text-gray-700">
                  Welcome, {session.user.name || session.user.email}
                </div>
                <Anchor href="/preferences">Preferences</Anchor>
                <Anchor href="/guide">Guide</Anchor>
                <Anchor href="https://www.opensanctions.org/impressum/">Impressum</Anchor>
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
              <>
                <Anchor href="/guide">Guide</Anchor>
                <Anchor href="https://www.opensanctions.org/impressum/">Impressum</Anchor>
                <Button
                  onClick={() => signIn('wikimedia')}
                  variant="ghost"
                  size="sm"
                  className="text-gray-600 hover:text-gray-800"
                >
                  Sign in
                </Button>
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  )
}
