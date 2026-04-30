import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, waitFor } from '@testing-library/react'
import { FirstLoginAutoDetect } from './FirstLoginAutoDetect'
import { UserProvider } from '@/contexts/UserContext'
import { EntityCatalogProvider } from '@/contexts/EntityCatalogContext'
import type { User } from '@/types'

function Tree() {
  return (
    <UserProvider>
      <EntityCatalogProvider>
        <FirstLoginAutoDetect />
      </EntityCatalogProvider>
    </UserProvider>
  )
}

const ENGLISH = {
  wikidata_id: 'Q1860',
  name: 'English',
  iso_639_1: 'en',
  iso_639_3: 'eng',
  sources_count: 1,
}

beforeEach(() => {
  Object.defineProperty(navigator, 'languages', {
    value: ['en-US'],
    configurable: true,
  })
})

/** Route fetch mocks by URL + method so test setup is order-independent. */
function setupRoutedFetch(routes: {
  user?: User | null
  languages?: unknown[]
  countries?: unknown[]
  patchOk?: boolean
}) {
  vi.mocked(fetch).mockImplementation(async (input, init) => {
    const url = typeof input === 'string' ? input : (input as Request).url
    const method = (init as RequestInit | undefined)?.method ?? 'GET'

    if (url === '/api/user' && method === 'GET') {
      return {
        ok: true,
        json: async () => routes.user ?? null,
      } as Response
    }
    if (url === '/api/user' && method === 'PATCH') {
      return {
        ok: routes.patchOk ?? true,
        json: async () => ({}),
      } as Response
    }
    if (url === '/api/languages') {
      return {
        ok: true,
        json: async () => routes.languages ?? [],
      } as Response
    }
    if (url === '/api/countries') {
      return {
        ok: true,
        json: async () => routes.countries ?? [],
      } as Response
    }
    throw new Error(`Unexpected fetch: ${method} ${url}`)
  })
}

function findPatchCall() {
  return vi
    .mocked(fetch)
    .mock.calls.find(
      ([url, init]) => url === '/api/user' && (init as RequestInit | undefined)?.method === 'PATCH',
    )
}

describe('FirstLoginAutoDetect', () => {
  it('PATCHes /user with detected languages when /user returns null', async () => {
    setupRoutedFetch({ user: null, languages: [ENGLISH], countries: [] })

    render(<Tree />)

    await waitFor(() => {
      expect(findPatchCall()).toBeDefined()
    })

    const patchCall = findPatchCall()!
    expect(JSON.parse((patchCall[1] as RequestInit).body as string)).toEqual({
      filters: { language: ['Q1860'] },
    })
  })

  it('PATCHes with empty list when no browser languages match the catalog', async () => {
    Object.defineProperty(navigator, 'languages', {
      value: ['xx-YY'],
      configurable: true,
    })
    setupRoutedFetch({ user: null, languages: [ENGLISH], countries: [] })

    render(<Tree />)

    await waitFor(() => {
      expect(findPatchCall()).toBeDefined()
    })

    const patchCall = findPatchCall()!
    expect(JSON.parse((patchCall[1] as RequestInit).body as string)).toEqual({
      filters: { language: [] },
    })
  })

  it('does not fire when /user returned a populated row', async () => {
    const populated: User = {
      settings: {
        advanced_mode: false,
        basic_tutorial_completed: false,
        advanced_tutorial_completed: false,
        stats_unlocked: false,
      },
      filters: { language: [], country: [] },
    }
    setupRoutedFetch({ user: populated, languages: [ENGLISH], countries: [] })

    render(<Tree />)

    // Allow effects to settle.
    await waitFor(() => {
      const calls = vi.mocked(fetch).mock.calls
      expect(calls.length).toBeGreaterThanOrEqual(3)
    })

    expect(findPatchCall()).toBeUndefined()
  })
})
