import '@testing-library/jest-dom'
import { vi, beforeEach } from 'vitest'
import { useSession } from 'next-auth/react'

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key]
    }),
    clear: vi.fn(() => {
      store = {}
    }),
  }
})()
Object.defineProperty(window, 'localStorage', { value: localStorageMock, writable: true })

// Mock next-auth/react — defaults to authenticated.
// restoreMocks only affects vi.spyOn(), not vi.fn() (https://vitest.dev/api/vi.html),
// so we use beforeEach to reset the default after each test.
vi.mock('next-auth/react', () => ({
  useSession: vi.fn(),
  SessionProvider: ({ children }: { children: React.ReactNode }) => children,
}))

// Mock @/auth
vi.mock('@/auth', () => ({
  signOut: vi.fn(),
  signIn: vi.fn(),
  auth: vi.fn(),
  handlers: { GET: vi.fn(), POST: vi.fn() },
}))

// Neither fetch nor EventSource exist in jsdom, so vi.spyOn is not possible.
global.fetch = vi.fn()

export let mockEventSource: {
  onmessage: ((e: MessageEvent) => void) | null
  onopen: (() => void) | null
  onerror: (() => void) | null
  close: ReturnType<typeof vi.fn>
}

const MockEventSource = vi.fn(function (this: typeof mockEventSource) {
  this.onmessage = null
  this.onopen = null
  this.onerror = null
  this.close = vi.fn()
  mockEventSource = this
})
vi.stubGlobal('EventSource', MockEventSource)

// Reset vi.fn() mocks that clearMocks/restoreMocks can't reach.
beforeEach(() => {
  vi.mocked(useSession).mockReturnValue({
    data: { user: { name: 'Test' }, expires: '' },
    status: 'authenticated',
    update: vi.fn(),
  })
})
