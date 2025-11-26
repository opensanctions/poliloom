'use client'

import { useSession, signOut, signIn } from 'next-auth/react'
import Image from 'next/image'
import Link from 'next/link'
import { Button } from '@/components/ui/Button'

export function Header() {
  const { data: session, status } = useSession()

  return (
    <header className="bg-white shadow-sm border-b sticky top-0 z-10">
      <div className="w-full pl-6 pr-4 sm:pr-6 lg:pr-8">
        <div className="flex justify-between items-center h-16">
          <div className="flex items-center">
            <Link href="/" className="flex items-center gap-2 text-xl font-bold text-gray-900">
              <Image
                src="https://assets.opensanctions.org/images/ep/logo-icon-color.svg"
                alt="European Parliament"
                width={128}
                height={128}
                className="h-8 w-8"
              />
              PoliLoom
            </Link>
          </div>

          <div className="flex items-center space-x-4">
            {status === 'authenticated' && session?.user && (
              <>
                <div className="text-sm text-gray-700">
                  Welcome, {session.user.name || session.user.email}
                </div>
                <a
                  href="https://www.opensanctions.org/impressum/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-2 py-1 text-sm text-gray-600 hover:text-gray-800 transition-colors font-medium"
                >
                  Impressum
                </a>
                <Button
                  onClick={() => signOut({ callbackUrl: '/' })}
                  variant="secondary"
                  size="small"
                >
                  Sign out
                </Button>
              </>
            )}

            {status === 'unauthenticated' && (
              <>
                <a
                  href="https://www.opensanctions.org/impressum/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-2 py-1 text-sm text-gray-600 hover:text-gray-800 transition-colors font-medium"
                >
                  Impressum
                </a>
                <Button
                  onClick={() => signIn('wikimedia', { callbackUrl: '/' })}
                  variant="secondary"
                  size="small"
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
