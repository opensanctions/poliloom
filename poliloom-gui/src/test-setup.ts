import '@testing-library/jest-dom'
import { vi } from 'vitest'

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

// Mock next-auth/react
vi.mock('next-auth/react', () => ({
  useSession: vi.fn(() => ({
    data: null,
    status: 'loading',
  })),
  SessionProvider: ({ children }: { children: React.ReactNode }) => children,
}))

// Mock @/auth
vi.mock('@/auth', () => ({
  signOut: vi.fn(),
  signIn: vi.fn(),
  auth: vi.fn(),
  handlers: { GET: vi.fn(), POST: vi.fn() },
}))

// Mock global fetch
global.fetch = vi.fn()
