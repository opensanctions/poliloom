'use client'

import { useState, useEffect, useRef } from 'react'
import { useSession, signOut, signIn } from 'next-auth/react'
import Image from 'next/image'
import Link from 'next/link'
import { Button } from '@/components/ui/Button'
import { SpinningCounter } from '@/components/ui/SpinningCounter'

export function Header() {
  const { status } = useSession()
  const [menuOpen, setMenuOpen] = useState(false)
  const [evaluationCount, setEvaluationCount] = useState<number | null>(null)

  useEffect(() => {
    if (status !== 'authenticated') return

    const fetchEvaluationCount = async () => {
      try {
        const response = await fetch('/api/stats/count')
        if (response.ok) {
          const data = await response.json()

          setEvaluationCount(data.total)
        }
      } catch {
        // Silently fail - counter just won't show
      }
    }

    fetchEvaluationCount()
    const interval = setInterval(fetchEvaluationCount, 2000)
    return () => clearInterval(interval)
  }, [status])

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
          priority
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
        {status === 'authenticated' && (
          <Button
            href="/stats"
            variant="secondary"
            size="small"
            className="max-md:text-lg max-md:py-4 max-md:px-6 max-md:justify-start"
          >
            <SpinningCounter value={evaluationCount ?? 0} className="mr-2" /> Evaluations
          </Button>
        )}
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
