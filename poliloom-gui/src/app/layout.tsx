import type { Metadata } from 'next'
import Script from 'next/script'
import './globals.css'
import { auth } from '@/auth'
import { SessionProvider } from '@/components/SessionProvider'
import { UserPreferencesProvider } from '@/contexts/UserPreferencesContext'
import { EvaluationSessionProvider } from '@/contexts/EvaluationSessionContext'
import { UserProgressProvider } from '@/contexts/UserProgressContext'
import { EvaluationCountProvider } from '@/contexts/EvaluationCountContext'
import { FetchInterceptor } from '@/components/FetchInterceptor'
import { MobileGuard } from '@/components/layout/MobileGuard'
import { Header } from '@/components/layout/Header'

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
  const session = await auth()

  return (
    <html lang="en">
      <head>
        <Script
          src="https://cloud.umami.is/script.js"
          data-website-id="0d1eaae6-470d-4087-9908-ec65448c2490"
          strategy="beforeInteractive"
        />
      </head>
      <body className="font-sans antialiased grid grid-rows-[auto_1fr] h-screen">
        <SessionProvider session={session}>
          <FetchInterceptor />
          <UserPreferencesProvider>
            <EvaluationSessionProvider>
              <UserProgressProvider>
                <EvaluationCountProvider>
                  <MobileGuard>
                    <Header />
                    {children}
                  </MobileGuard>
                </EvaluationCountProvider>
              </UserProgressProvider>
            </EvaluationSessionProvider>
          </UserPreferencesProvider>
        </SessionProvider>
      </body>
    </html>
  )
}
