import { NextRequest, NextResponse } from 'next/server'
import { auth } from '@/auth'
import {
  FILTER_LANGUAGES_COOKIE,
  FILTER_COUNTRIES_COOKIE,
  serializeFilterCookieValue,
} from './lib/cookies'

const ONE_YEAR_SECONDS = 60 * 60 * 24 * 365

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

export default auth((req) => {
  const isAuthenticated = !!req.auth && !req.auth.error
  const pathname = req.nextUrl.pathname

  // Redirect unauthenticated users to login, preserving the original URL
  if (!isAuthenticated && pathname !== '/login') {
    const loginUrl = new URL('/login', req.nextUrl.origin)
    loginUrl.searchParams.set('redirect', req.nextUrl.pathname + req.nextUrl.search)
    const response = NextResponse.redirect(loginUrl)
    applyFilterCookies(req, response)
    return response
  }

  // Redirect authenticated users without a Wikidata account to setup
  if (isAuthenticated && !req.auth?.hasWikidataAccount && pathname !== '/setup') {
    const response = NextResponse.redirect(new URL('/setup', req.nextUrl.origin))
    applyFilterCookies(req, response)
    return response
  }

  // Strip filter query params from the URL after persisting them to cookies
  if (hasFilterParams(req)) {
    const cleaned = stripFilterParams(req.nextUrl)
    const response = NextResponse.redirect(cleaned)
    applyFilterCookies(req, response)
    return response
  }

  const response = NextResponse.next({ request: { headers: req.headers } })
  applyFilterCookies(req, response)
  return response
})

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - api (API routes handle their own auth and don't need filter cookies)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     */
    '/((?!api|_next/static|_next/image|favicon.ico).*)',
  ],
}
