import { vi } from 'vitest'

// Mock useAuthSession to avoid next-auth SessionProvider dependency
vi.mock('@/hooks/useAuthSession', () => ({
  useAuthSession: () => ({
    session: { accessToken: 'mock-token' },
    status: 'authenticated',
    isAuthenticated: true,
  }),
}))

// Mock Next.js router
export const mockRouterPush = vi.fn()
export const mockRouterPrefetch = vi.fn()
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockRouterPush,
    replace: vi.fn(),
    back: vi.fn(),
    prefetch: mockRouterPrefetch,
  }),
}))

// Mock fetch for tests that need to verify API calls
export const mockFetch = vi.fn().mockResolvedValue({
  ok: true,
  json: async () => ({ success: true }),
})
global.fetch = mockFetch as unknown as typeof fetch

// Mock functions exported for test assertions
export const mockSubmitAndAdvance = vi.fn().mockReturnValue({ sessionComplete: false })
export const mockStartSession = vi.fn()
export const mockEndSession = vi.fn()
