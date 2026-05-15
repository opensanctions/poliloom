import type { Metadata } from 'next'
import { cookies } from 'next/headers'
import { THEME_COOKIE, deserializeThemeCookieValue } from '@/lib/cookies'
import './globals.css'
import { SessionProvider } from 'next-auth/react'
import { ThemeProvider } from '@/contexts/ThemeContext'
import { MobileGuard } from '@/components/layout/MobileGuard'

export const metadata: Metadata = {
  title: 'PoliLoom - Verify Political Data',
  description:
    'Help build accurate, open political data. Evaluate politician information extracted from Wikipedia and government sources before it becomes part of the open knowledge commons.',
  icons: {
    icon: 'https://assets.opensanctions.org/images/ep/favicon-32.png',
    apple: 'https://assets.opensanctions.org/images/ep/logo-icon-color.png',
  },
}

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  const cookieStore = await cookies()
  const themeCookie = deserializeThemeCookieValue(cookieStore.get(THEME_COOKIE)?.value)
  const themeClass = themeCookie ?? ''

  return (
    <html lang="en" className={themeClass} suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              if (!document.documentElement.classList.contains('light') && !document.documentElement.classList.contains('dark')) {
                document.documentElement.classList.add(
                  window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
                );
              }
            `,
          }}
        />
      </head>
      <body className="font-sans antialiased grid grid-rows-[auto_1fr] h-screen">
        <SessionProvider>
          <ThemeProvider>
            <MobileGuard>{children}</MobileGuard>
          </ThemeProvider>
        </SessionProvider>
      </body>
    </html>
  )
}
