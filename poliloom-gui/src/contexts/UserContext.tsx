'use client'

import React, { createContext, useCallback, useContext, useRef, useState } from 'react'
import { User, UserPatchInput, WikidataEntity } from '@/types'

interface UserContextType {
  user: User | null
  patch: (body: UserPatchInput) => Promise<void>
  // true while any PATCH is in flight; barrier for downstream fetches
  pending: boolean
}

const UserContext = createContext<UserContextType | undefined>(undefined)

function applyPatch(prev: User, body: UserPatchInput): User {
  const settings = body.settings ? { ...prev.settings, ...body.settings } : prev.settings
  let filters = prev.filters
  if (body.filters) {
    filters = {
      language: body.filters.language ?? prev.filters.language,
      country: body.filters.country ?? prev.filters.country,
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

export function UserProvider({
  initialUser,
  children,
}: {
  initialUser: User | null
  children: React.ReactNode
}) {
  const [user, setUser] = useState<User | null>(initialUser)
  const [inflight, setInflight] = useState(0)
  // Mirror current user in a ref so patch() captures a synchronous snapshot
  // for optimistic-rollback without re-deriving the callback on every change.
  const userRef = useRef<User | null>(initialUser)

  const setUserSynced = useCallback((next: User | null) => {
    userRef.current = next
    setUser(next)
  }, [])

  const patch = useCallback(
    async (body: UserPatchInput) => {
      const snapshot = userRef.current
      if (snapshot === null) return // unauthenticated; nothing to patch
      setUserSynced(applyPatch(snapshot, body))
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
