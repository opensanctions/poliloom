import { auth } from '@/auth'

export default auth((req) => {
  const isAuthenticated = !!req.auth && !req.auth.error
  const pathname = req.nextUrl.pathname

  // Redirect unauthenticated users to login
  if (!isAuthenticated && pathname !== '/login') {
    return Response.redirect(new URL('/login', req.nextUrl.origin))
  }

  // Redirect authenticated users without a Wikidata account to setup
  if (isAuthenticated && !req.auth?.hasWikidataAccount && pathname !== '/setup') {
    return Response.redirect(new URL('/setup', req.nextUrl.origin))
  }
})

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - api/auth (auth API routes)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     */
    '/((?!api/auth|_next/static|_next/image|favicon.ico).*)',
  ],
}
