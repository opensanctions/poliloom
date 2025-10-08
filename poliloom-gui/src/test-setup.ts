import '@testing-library/jest-dom'
import { vi } from 'vitest'

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
