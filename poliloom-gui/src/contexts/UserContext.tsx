'use client'

import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { useSession } from 'next-auth/react'
import { User, UserPatchInput, WikidataEntity } from '@/types'

interface UserContextType {
  // undefined: GET in flight; null: no row (first login); object: loaded
  user: User | null | undefined
  patch: (body: UserPatchInput) => Promise<void>
  pending: boolean
}

const UserContext = createContext<UserContextType | undefined>(undefined)

const DEFAULT_USER: User = {
  settings: {
    advanced_mode: false,
    basic_tutorial_completed: false,
    advanced_tutorial_completed: false,
    stats_unlocked: false,
  },
  filters: { language: [], country: [] },
}

function applyPatch(prev: User | null, body: UserPatchInput): User {
  const base: User = prev ?? DEFAULT_USER

  const settings = body.settings ? { ...base.settings, ...body.settings } : base.settings

  let filters = base.filters
  if (body.filters) {
    filters = {
      language: body.filters.language ?? base.filters.language,
      country: body.filters.country ?? base.filters.country,
    }
  }

  return { settings, filters }
}

function toWirePayload(body: UserPatchInput) {
  const wire: {
    settings?: UserPatchInput['settings']
    filters?: { language?: string[]; country?: string[] }
  } = {}
  if (body.settings) wire.settings = body.settings
  if (body.filters) {
    const f: { language?: string[]; country?: string[] } = {}
    if (body.filters.language)
      f.language = body.filters.language.map((e: WikidataEntity) => e.wikidata_id)
    if (body.filters.country)
      f.country = body.filters.country.map((e: WikidataEntity) => e.wikidata_id)
    wire.filters = f
  }
  return wire
}

export function UserProvider({ children }: { children: React.ReactNode }) {
  const { status } = useSession()
  const [user, setUser] = useState<User | null | undefined>(undefined)
  const [inflight, setInflight] = useState(0)
  // Mirror current user in a ref so patch() captures a synchronous snapshot
  // for optimistic-rollback without re-deriving the callback on every change.
  const userRef = useRef<User | null | undefined>(undefined)
  const fetched = useRef(false)

  const setUserSynced = useCallback((next: User | null | undefined) => {
    userRef.current = next
    setUser(next)
  }, [])

  useEffect(() => {
    if (status !== 'authenticated' || fetched.current) return
    fetched.current = true
    ;(async () => {
      try {
        const response = await fetch('/api/user')
        if (!response.ok) throw new Error(`GET /api/user: ${response.status}`)
        const data = (await response.json()) as User | null
        setUserSynced(data)
      } catch (error) {
        console.warn('Failed to load user state:', error)
      }
    })()
  }, [status, setUserSynced])

  const patch = useCallback(
    async (body: UserPatchInput) => {
      const snapshot = userRef.current
      setUserSynced(applyPatch(snapshot ?? null, body))
      setInflight((c) => c + 1)
      try {
        const response = await fetch('/api/user', {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(toWirePayload(body)),
        })
        if (!response.ok) throw new Error(`PATCH /api/user: ${response.status}`)
        // Server response is intentionally discarded: the optimistic merge is
        // the source of truth here so overlapping PATCHes don't clobber each other.
      } catch (error) {
        console.warn('PATCH /api/user failed; reverting:', error)
        setUserSynced(snapshot)
      } finally {
        setInflight((c) => c - 1)
      }
    },
    [setUserSynced],
  )

  return (
    <UserContext.Provider value={{ user, patch, pending: inflight > 0 }}>
      {children}
    </UserContext.Provider>
  )
}

export function useUser() {
  const context = useContext(UserContext)
  if (context === undefined) {
    throw new Error('useUser must be used within a UserProvider')
  }
  return context
}
