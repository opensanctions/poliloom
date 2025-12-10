import type { Metadata } from 'next'
import './globals.css'
import { auth } from '@/auth'
import { SessionProvider } from '@/components/SessionProvider'
import { UserPreferencesProvider } from '@/contexts/UserPreferencesContext'
import { EvaluationSessionProvider } from '@/contexts/EvaluationSessionContext'
import { TutorialProvider } from '@/contexts/TutorialContext'
import { FetchInterceptor } from '@/components/FetchInterceptor'

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
      <body className="font-sans antialiased grid grid-rows-[auto_1fr] h-screen">
        <SessionProvider session={session}>
          <FetchInterceptor />
          <UserPreferencesProvider>
            <EvaluationSessionProvider>
              <TutorialProvider>{children}</TutorialProvider>
            </EvaluationSessionProvider>
          </UserPreferencesProvider>
        </SessionProvider>
      </body>
    </html>
  )
}
