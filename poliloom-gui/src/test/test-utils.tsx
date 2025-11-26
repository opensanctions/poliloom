import React, { ReactElement } from 'react'
import { render, RenderOptions } from '@testing-library/react'
import { vi } from 'vitest'
import { UserPreferencesProvider } from '@/contexts/UserPreferencesContext'
import { TutorialProvider } from '@/contexts/TutorialContext'
import { EvaluationSessionProvider } from '@/contexts/EvaluationSessionContext'

// Mock useAuthSession to avoid next-auth SessionProvider dependency
vi.mock('@/hooks/useAuthSession', () => ({
  useAuthSession: () => ({
    session: { accessToken: 'mock-token' },
    status: 'authenticated',
    isAuthenticated: true,
  }),
}))

// Mock fetch globally for provider API calls
const mockFetch = vi.fn()

// Set default implementation (can be overridden in tests)
mockFetch.mockImplementation((url: string) => {
  if (url.includes('/api/languages')) {
    return Promise.resolve({ ok: true, json: async () => [] })
  }
  if (url.includes('/api/countries')) {
    return Promise.resolve({ ok: true, json: async () => [] })
  }
  if (url.includes('/api/politicians')) {
    return Promise.resolve({ ok: true, json: async () => [] })
  }
  if (url.includes('/api/evaluations')) {
    return Promise.resolve({ ok: true, json: async () => ({ success: true }) })
  }
  return Promise.resolve({ ok: true, json: async () => [] })
})
global.fetch = mockFetch as unknown as typeof fetch

export { mockFetch }

const AllTheProviders = ({ children }: { children: React.ReactNode }) => {
  return (
    <TutorialProvider>
      <UserPreferencesProvider>
        <EvaluationSessionProvider>{children}</EvaluationSessionProvider>
      </UserPreferencesProvider>
    </TutorialProvider>
  )
}

const customRender = (ui: ReactElement, options?: Omit<RenderOptions, 'wrapper'>) =>
  render(ui, { wrapper: AllTheProviders, ...options })

export * from '@testing-library/react'
export { customRender as render }
