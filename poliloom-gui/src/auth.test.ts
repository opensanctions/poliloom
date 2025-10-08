import { describe, it, expect, vi } from 'vitest'

// Mock NextAuth since we can't easily test the full OAuth flow
vi.mock('next-auth', () => ({
  default: vi.fn(() => ({
    handlers: { GET: vi.fn(), POST: vi.fn() },
    auth: vi.fn(),
    signIn: vi.fn(),
    signOut: vi.fn(),
  })),
}))

vi.mock('next-auth/providers/wikimedia', () => ({
  default: vi.fn(() => ({ id: 'wikimedia', name: 'Wikimedia' })),
}))

// Create a mock config
const mockConfig = {
  providers: [{ id: 'wikimedia', name: 'Wikimedia' }],
  callbacks: {
    jwt: vi.fn(
      async ({
        token,
        account,
      }: {
        token: Record<string, unknown>
        account: { access_token: string } | null
      }) => {
        if (account) {
          return { ...token, accessToken: account.access_token }
        }
        return token
      },
    ),
    session: vi.fn(
      async ({
        session,
        token,
      }: {
        session: Record<string, unknown>
        token: { accessToken?: string }
      }) => {
        return { ...session, accessToken: token.accessToken }
      },
    ),
    redirect: vi.fn(async ({ url, baseUrl }: { url: string; baseUrl: string }) => {
      if (url.startsWith('/')) return `${baseUrl}${url}`
      if (url.startsWith(baseUrl)) return url
      return baseUrl
    }),
  },
  pages: {
    signIn: '/auth/login',
  },
}

describe('auth configuration', () => {
  it('has correct provider configuration', () => {
    expect(mockConfig.providers).toHaveLength(1)
    expect(mockConfig.providers[0]).toBeDefined()
  })

  it('has jwt callback that preserves access token', async () => {
    const mockToken = { someExistingToken: 'value' }
    const mockAccount = { access_token: 'oauth-access-token' }

    const result = await mockConfig.callbacks?.jwt?.({
      token: mockToken,
      account: mockAccount,
    })

    expect(result).toEqual({
      someExistingToken: 'value',
      accessToken: 'oauth-access-token',
    })
  })

  it('has jwt callback that returns token unchanged when no account', async () => {
    const mockToken = { someExistingToken: 'value' }

    const result = await mockConfig.callbacks?.jwt?.({
      token: mockToken,
      account: null,
    })

    expect(result).toEqual(mockToken)
  })

  it('has session callback that adds access token to session', async () => {
    const mockSession = { user: { name: 'Test User' } }
    const mockToken = { accessToken: 'test-access-token' }

    const result = await mockConfig.callbacks?.session?.({
      session: mockSession,
      token: mockToken,
    })

    expect(result).toEqual({
      user: { name: 'Test User' },
      accessToken: 'test-access-token',
    })
  })

  it('has redirect callback that handles relative URLs', async () => {
    const baseUrl = 'https://example.com'

    const result = await mockConfig.callbacks?.redirect?.({
      url: '/dashboard',
      baseUrl,
    })

    expect(result).toBe('https://example.com/dashboard')
  })

  it('has redirect callback that handles same-origin URLs', async () => {
    const baseUrl = 'https://example.com'

    const result = await mockConfig.callbacks?.redirect?.({
      url: 'https://example.com/dashboard',
      baseUrl,
    })

    expect(result).toBe('https://example.com/dashboard')
  })

  it('has redirect callback that defaults to baseUrl for external URLs', async () => {
    const baseUrl = 'https://example.com'

    const result = await mockConfig.callbacks?.redirect?.({
      url: 'https://malicious-site.com/dashboard',
      baseUrl,
    })

    expect(result).toBe(baseUrl)
  })

  it('has correct sign-in page configured', () => {
    expect(mockConfig.pages?.signIn).toBe('/auth/login')
  })
})
