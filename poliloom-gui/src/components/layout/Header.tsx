'use client'

import { useState, useEffect } from 'react'
import { useSession, signOut, signIn } from 'next-auth/react'
import Image from 'next/image'
import Link from 'next/link'
import { Button } from '@/components/ui/Button'

export function Header() {
  const { data: session, status } = useSession()
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    if (!menuOpen) return
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMenuOpen(false)
    }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [menuOpen])

  return (
    <header className="flex justify-between items-center h-16 px-6 bg-white shadow-sm border-b sticky top-0 z-10">
      <Link href="/" className="flex items-center gap-2 text-xl font-bold text-gray-900">
        <Image
          src="https://assets.opensanctions.org/images/ep/logo-icon-color.svg"
          alt="European Parliament"
          width={32}
          height={32}
          className="h-8 w-8"
        />
        PoliLoom
      </Link>

      <button
        className="md:hidden flex flex-col justify-center gap-[5px] w-10 h-10 p-2 -mr-2"
        onClick={() => setMenuOpen(!menuOpen)}
        aria-expanded={menuOpen}
        aria-controls="main-nav"
        aria-label={menuOpen ? 'Close menu' : 'Open menu'}
      >
        <span
          className={`block w-6 h-0.5 bg-gray-600 transition-transform duration-300 ${menuOpen ? 'translate-y-[7px] rotate-45' : ''}`}
        />
        <span
          className={`block w-6 h-0.5 bg-gray-600 transition-opacity duration-300 ${menuOpen ? 'opacity-0' : ''}`}
        />
        <span
          className={`block w-6 h-0.5 bg-gray-600 transition-transform duration-300 ${menuOpen ? '-translate-y-[7px] -rotate-45' : ''}`}
        />
      </button>

      <nav
        id="main-nav"
        className={`flex items-center gap-4 max-md:fixed max-md:inset-0 max-md:top-16 max-md:flex-col max-md:items-stretch max-md:gap-0 max-md:bg-white max-md:pt-4 ${menuOpen ? '' : 'max-md:hidden'}`}
      >
        {status === 'authenticated' && session?.user && (
          <span className="text-sm text-gray-700 font-medium max-md:hidden">
            Welcome, {session.user.name || session.user.email}
          </span>
        )}
        <Button
          href="/stats"
          variant="secondary"
          size="small"
          className="max-md:text-lg max-md:py-4 max-md:px-6 max-md:justify-start"
        >
          Stats
        </Button>
        <Button
          href="https://www.opensanctions.org/impressum/"
          variant="secondary"
          size="small"
          className="max-md:text-lg max-md:py-4 max-md:px-6 max-md:justify-start"
        >
          Impressum
        </Button>
        {status === 'authenticated' ? (
          <Button
            onClick={() => signOut({ callbackUrl: '/' })}
            variant="secondary"
            size="small"
            className="max-md:text-lg max-md:py-4 max-md:px-6 max-md:justify-start"
          >
            Sign out
          </Button>
        ) : status === 'unauthenticated' ? (
          <Button
            onClick={() => signIn('wikimedia', { callbackUrl: '/' })}
            variant="secondary"
            size="small"
            className="max-md:text-lg max-md:py-4 max-md:px-6 max-md:justify-start"
          >
            Sign in
          </Button>
        ) : null}
      </nav>
    </header>
  )
}
