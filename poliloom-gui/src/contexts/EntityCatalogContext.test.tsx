import { describe, it, expect, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { EntityCatalogProvider, useEntityCatalog } from './EntityCatalogContext'

function wrapper({ children }: { children: React.ReactNode }) {
  return <EntityCatalogProvider>{children}</EntityCatalogProvider>
}

function mockOk<T>(value: T) {
  vi.mocked(fetch).mockImplementationOnce(
    async () =>
      ({
        ok: true,
        json: async () => value,
      }) as Response,
  )
}

describe('EntityCatalogContext', () => {
  it('fetches languages and countries on mount', async () => {
    mockOk([{ wikidata_id: 'Q1860', name: 'English', sources_count: 5 }])
    mockOk([{ wikidata_id: 'Q30', name: 'United States', citizenships_count: 10 }])

    const { result } = renderHook(() => useEntityCatalog(), { wrapper })

    await waitFor(() => {
      expect(result.current.loadingLanguages).toBe(false)
      expect(result.current.loadingCountries).toBe(false)
    })

    expect(result.current.languages).toEqual([
      { wikidata_id: 'Q1860', name: 'English', sources_count: 5 },
    ])
    expect(result.current.countries).toEqual([
      { wikidata_id: 'Q30', name: 'United States', citizenships_count: 10 },
    ])
    expect(fetch).toHaveBeenCalledWith('/api/languages')
    expect(fetch).toHaveBeenCalledWith('/api/countries')
  })

  it('clears loading flags when fetch fails', async () => {
    vi.mocked(fetch).mockRejectedValue(new Error('boom'))

    const { result } = renderHook(() => useEntityCatalog(), { wrapper })

    await waitFor(() => {
      expect(result.current.loadingLanguages).toBe(false)
      expect(result.current.loadingCountries).toBe(false)
    })
    expect(result.current.languages).toEqual([])
    expect(result.current.countries).toEqual([])
  })

  it('throws when used outside provider', () => {
    expect(() => renderHook(() => useEntityCatalog())).toThrow(
      'useEntityCatalog must be used within an EntityCatalogProvider',
    )
  })
})
