import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function middleware(request: NextRequest) {
  console.log('=== MIDDLEWARE EXECUTING ===')
  console.log('Path:', request.nextUrl.pathname)

  // Test: Just redirect / and /evaluate to /login unconditionally for now
  const pathname = request.nextUrl.pathname

  if (pathname === '/' || pathname === '/evaluate') {
    console.log('Redirecting to /login from:', pathname)
    const loginUrl = new URL('/login', request.url)
    loginUrl.searchParams.set('callbackUrl', pathname)
    return NextResponse.redirect(loginUrl)
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/', '/evaluate'],
}
