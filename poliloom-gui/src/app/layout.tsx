import type { Metadata } from 'next'
import './globals.css'
import { auth } from '@/auth'
import { SessionProvider } from '@/components/SessionProvider'
import { EvaluationFiltersProvider } from '@/contexts/EvaluationFiltersContext'
import { EvaluationProvider } from '@/contexts/EvaluationContext'
import { TutorialProvider } from '@/contexts/TutorialContext'
import { FetchInterceptor } from '@/components/FetchInterceptor'

export const metadata: Metadata = {
  title: 'PoliLoom - Verify Political Data',
  description:
    'Help build accurate, open political data. Review and confirm politician information extracted from Wikipedia and government sources before it becomes part of the open knowledge commons.',
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
          <EvaluationFiltersProvider>
            <EvaluationProvider>
              <TutorialProvider>{children}</TutorialProvider>
            </EvaluationProvider>
          </EvaluationFiltersProvider>
        </SessionProvider>
      </body>
    </html>
  )
}
