'use client'

import { useState, useEffect, useSyncExternalStore } from 'react'
import { useSession, signOut, signIn } from 'next-auth/react'
import Image from 'next/image'
import Link from 'next/link'
import { Button } from '@/components/ui/Button'
import { SpinningCounter } from '@/components/ui/SpinningCounter'
import { useEvaluationCount } from '@/contexts/EvaluationCountContext'
import { useUserPreferences } from '@/contexts/UserPreferencesContext'

export function Header() {
  const { status } = useSession()
  const [menuOpen, setMenuOpen] = useState(false)
  const { evaluationCount } = useEvaluationCount()
  const { theme, setTheme } = useUserPreferences()
  const systemTheme = useSyncExternalStore(
    (cb) => {
      const mq = window.matchMedia('(prefers-color-scheme: dark)')
      mq.addEventListener('change', cb)
      return () => mq.removeEventListener('change', cb)
    },
    () => (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'),
    () => 'light',
  )
  const resolvedTheme = theme ?? systemTheme

  const toggleTheme = () => {
    setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')
  }

  useEffect(() => {
    if (!menuOpen) return
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMenuOpen(false)
    }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [menuOpen])

  return (
    <header className="flex justify-between items-center h-16 px-6 bg-surface shadow-sm border-b border-border sticky top-0 z-10">
      <Link href="/" className="flex items-center gap-2 text-xl font-bold text-foreground">
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
          className={`block w-6 h-0.5 bg-foreground-muted transition-transform duration-300 ${menuOpen ? 'translate-y-[7px] rotate-45' : ''}`}
        />
        <span
          className={`block w-6 h-0.5 bg-foreground-muted transition-opacity duration-300 ${menuOpen ? 'opacity-0' : ''}`}
        />
        <span
          className={`block w-6 h-0.5 bg-foreground-muted transition-transform duration-300 ${menuOpen ? '-translate-y-[7px] -rotate-45' : ''}`}
        />
      </button>

      <nav
        id="main-nav"
        className={`flex items-center gap-4 max-md:fixed max-md:inset-0 max-md:top-16 max-md:flex-col max-md:items-stretch max-md:gap-0 max-md:bg-surface max-md:pt-4 ${menuOpen ? '' : 'max-md:hidden'}`}
      >
        {status === 'authenticated' && (
          <Button
            href="/stats"
            variant="secondary"
            size="small"
            className="max-md:text-lg max-md:py-4 max-md:px-6 max-md:justify-start"
          >
            <SpinningCounter
              value={evaluationCount ?? 0}
              title="Total accepted and rejected statements"
            />
          </Button>
        )}
        <Button
          onClick={toggleTheme}
          variant="secondary"
          size="small"
          title={`Switch to ${resolvedTheme === 'dark' ? 'light' : 'dark'} mode`}
          aria-label={`Switch to ${resolvedTheme === 'dark' ? 'light' : 'dark'} mode`}
        >
          {resolvedTheme === 'dark' ? (
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="currentColor"
              className="w-4 h-4"
            >
              <path d="M21.752 15.002A9.72 9.72 0 0 1 18 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 0 0 3 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 0 0 9.002-5.998Z" />
            </svg>
          ) : (
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="currentColor"
              className="w-4 h-4"
            >
              <path d="M12 2.25a.75.75 0 0 1 .75.75v2.25a.75.75 0 0 1-1.5 0V3a.75.75 0 0 1 .75-.75ZM7.5 12a4.5 4.5 0 1 1 9 0 4.5 4.5 0 0 1-9 0ZM18.894 6.166a.75.75 0 0 0-1.06-1.06l-1.591 1.59a.75.75 0 1 0 1.06 1.061l1.591-1.59ZM21.75 12a.75.75 0 0 1-.75.75h-2.25a.75.75 0 0 1 0-1.5H21a.75.75 0 0 1 .75.75ZM17.834 18.894a.75.75 0 0 0 1.06-1.06l-1.59-1.591a.75.75 0 1 0-1.061 1.06l1.591 1.591ZM12 18a.75.75 0 0 1 .75.75V21a.75.75 0 0 1-1.5 0v-2.25A.75.75 0 0 1 12 18ZM7.758 17.303a.75.75 0 0 0-1.061-1.06l-1.591 1.59a.75.75 0 0 0 1.06 1.061l1.591-1.59ZM6 12a.75.75 0 0 1-.75.75H3a.75.75 0 0 1 0-1.5h2.25A.75.75 0 0 1 6 12ZM6.697 7.757a.75.75 0 0 0 1.06-1.06l-1.59-1.591a.75.75 0 0 0-1.061 1.06l1.59 1.591Z" />
            </svg>
          )}
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
