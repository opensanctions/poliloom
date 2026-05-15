import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/auth'
import {
  FILTER_LANGUAGES_COOKIE,
  FILTER_COUNTRIES_COOKIE,
  serializeFilterCookieValue,
} from './lib/cookies'

const ONE_YEAR_SECONDS = 60 * 60 * 24 * 365
const ACCESS_TOKEN_HEADER = 'x-access-token'

function getQidsFromParam(request: NextRequest, key: string): string[] | null {
  if (!request.nextUrl.searchParams.has(key)) {
    return null
  }
  const values = request.nextUrl.searchParams.getAll(key)
  if (values.length === 1 && values[0] === '') {
    return []
  }
  return values.filter((v) => v !== '')
}

const FILTER_PARAMS = ['languages', 'countries']

export function applyFilterCookies(request: NextRequest, response: NextResponse) {
  const languages = getQidsFromParam(request, 'languages')
  if (languages !== null) {
    response.cookies.set(FILTER_LANGUAGES_COOKIE, serializeFilterCookieValue(languages), {
      path: '/',
      sameSite: 'lax',
      maxAge: ONE_YEAR_SECONDS,
    })
  }

  const countries = getQidsFromParam(request, 'countries')
  if (countries !== null) {
    response.cookies.set(FILTER_COUNTRIES_COOKIE, serializeFilterCookieValue(countries), {
      path: '/',
      sameSite: 'lax',
      maxAge: ONE_YEAR_SECONDS,
    })
  }
}

/** Returns true when the request URL contains any filter query params. */
function hasFilterParams(request: NextRequest): boolean {
  return FILTER_PARAMS.some((key) => request.nextUrl.searchParams.has(key))
}

/** Strip filter query params from the URL, preserving everything else. */
function stripFilterParams(url: URL): URL {
  const cleaned = new URL(url.toString())
  for (const key of FILTER_PARAMS) {
    cleaned.searchParams.delete(key)
  }
  return cleaned
}

function isApiRoute(pathname: string): boolean {
  return pathname.startsWith('/api/')
}

export default auth((req) => {
  const isAuthenticated = !!req.auth && !req.auth.error
  const pathname = req.nextUrl.pathname
  const isApi = isApiRoute(pathname)

  // Unauthenticated: API routes get 401 JSON, pages get a redirect to /login.
  if (!isAuthenticated && pathname !== '/login') {
    if (isApi) {
      return NextResponse.json({ message: 'Not authenticated' }, { status: 401 })
    }
    const loginUrl = new URL('/login', req.nextUrl.origin)
    loginUrl.searchParams.set('redirect', req.nextUrl.pathname + req.nextUrl.search)
    const response = NextResponse.redirect(loginUrl)
    applyFilterCookies(req, response)
    return response
  }

  // Authenticated user hitting /login → bounce them home.
  if (isAuthenticated && pathname === '/login') {
    const redirect = req.nextUrl.searchParams.get('redirect') || '/'
    return NextResponse.redirect(new URL(redirect, req.nextUrl.origin))
  }

  // Authenticated but no linked Wikidata account → setup.
  if (isAuthenticated && !req.auth?.hasWikidataAccount && pathname !== '/setup') {
    if (isApi) {
      return NextResponse.json({ message: 'Wikidata account required' }, { status: 403 })
    }
    const response = NextResponse.redirect(new URL('/setup', req.nextUrl.origin))
    applyFilterCookies(req, response)
    return response
  }

  // Strip filter query params from the URL after persisting them to cookies.
  // Only for page navigations — API routes pass filter params through to handlers.
  if (!isApi && hasFilterParams(req)) {
    const cleaned = stripFilterParams(req.nextUrl)
    const response = NextResponse.redirect(cleaned)
    applyFilterCookies(req, response)
    return response
  }

  // Strip any client-supplied access token header, then inject the one from the
  // (possibly refreshed) session. This is the only channel through which the
  // server-side token reaches downstream handlers — they never call auth() again.
  const headers = new Headers(req.headers)
  headers.delete(ACCESS_TOKEN_HEADER)
  if (isAuthenticated && req.auth?.accessToken) {
    headers.set(ACCESS_TOKEN_HEADER, req.auth.accessToken)
  }
  const response = NextResponse.next({ request: { headers } })
  applyFilterCookies(req, response)
  return response
})

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - api/auth (NextAuth's own routes manage their own auth flow)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     *
     * /api/* is included so token refresh happens once per request and the
     * access token is injected as an internal header for the proxy handlers.
     */
    '/((?!api/auth|_next/static|_next/image|favicon.ico).*)',
  ],
}
