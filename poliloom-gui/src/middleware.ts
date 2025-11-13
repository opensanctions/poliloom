import { auth } from '@/auth'

export default auth((req) => {
  const isAuthenticated = !!req.auth
  const pathname = req.nextUrl.pathname

  // Public routes that don't require authentication
  const publicRoutes = ['/login', '/guide']
  const isPublicRoute = publicRoutes.some((route) => pathname.startsWith(route))

  // Redirect unauthenticated users on protected routes to login
  if (!isAuthenticated && !isPublicRoute) {
    const newUrl = new URL('/login', req.nextUrl.origin)
    return Response.redirect(newUrl)
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
