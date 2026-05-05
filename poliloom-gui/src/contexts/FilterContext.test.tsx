import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { FilterProvider, useFilters } from './FilterContext'
import { FILTER_COUNTRIES_COOKIE, FILTER_LANGUAGES_COOKIE, readFilterCookie } from '@/lib/cookies'

vi.mock('next/navigation', () => ({
  useRouter: () => ({}),
  usePathname: () => '/',
  useSearchParams: () => new URLSearchParams(),
}))

function clearCookies() {
  for (const c of document.cookie.split(';')) {
    const name = c.split('=')[0].trim()
    if (name) document.cookie = `${name}=; Max-Age=0; Path=/`
  }
}

function makeWrapper(opts: { initialLanguageQids?: string[]; initialCountryQids?: string[] }) {
  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <FilterProvider
      initialLanguageQids={opts.initialLanguageQids ?? []}
      initialCountryQids={opts.initialCountryQids ?? []}
    >
      {children}
    </FilterProvider>
  )
  Wrapper.displayName = 'FilterTestWrapper'
  return Wrapper
}

beforeEach(() => {
  clearCookies()
})

describe('FilterContext', () => {
  it('seeds state from initial QID props', () => {
    const { result } = renderHook(() => useFilters(), {
      wrapper: makeWrapper({ initialLanguageQids: ['Q1860'], initialCountryQids: ['Q30'] }),
    })
    expect(result.current.languageQids).toEqual(['Q1860'])
    expect(result.current.countryQids).toEqual(['Q30'])
  })

  it('setLanguages writes the cookie and updates state', () => {
    const { result } = renderHook(() => useFilters(), { wrapper: makeWrapper({}) })
    act(() => {
      result.current.setLanguages(['Q1860', 'Q7411'])
    })
    expect(result.current.languageQids).toEqual(['Q1860', 'Q7411'])
    expect(readFilterCookie(FILTER_LANGUAGES_COOKIE)).toEqual(['Q1860', 'Q7411'])
  })

  it('setLanguages([]) writes the cookie (preserves "explicitly cleared" state)', () => {
    const { result } = renderHook(() => useFilters(), {
      wrapper: makeWrapper({ initialLanguageQids: ['Q1860'] }),
    })
    act(() => {
      result.current.setLanguages([])
    })
    expect(result.current.languageQids).toEqual([])
    expect(document.cookie).toContain(FILTER_LANGUAGES_COOKIE)
    expect(readFilterCookie(FILTER_LANGUAGES_COOKIE)).toEqual([])
  })

  it('setCountries writes the cookie and updates state', () => {
    const { result } = renderHook(() => useFilters(), { wrapper: makeWrapper({}) })
    act(() => {
      result.current.setCountries(['Q30'])
    })
    expect(result.current.countryQids).toEqual(['Q30'])
    expect(readFilterCookie(FILTER_COUNTRIES_COOKIE)).toEqual(['Q30'])
  })

  it('throws when used outside provider', () => {
    expect(() => renderHook(() => useFilters())).toThrow(
      'useFilters must be used within a FilterProvider',
    )
  })
})
