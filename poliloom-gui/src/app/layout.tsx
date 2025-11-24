import type { Metadata } from 'next'
import './globals.css'
import { auth } from '@/auth'
import { SessionProvider } from '@/components/SessionProvider'
import { ArchivedPageProvider } from '@/contexts/ArchivedPageContext'
import { EvaluationFiltersProvider } from '@/contexts/EvaluationFiltersContext'
import { EvaluationProvider } from '@/contexts/EvaluationContext'
import { FetchInterceptor } from '@/components/FetchInterceptor'

export const metadata: Metadata = {
  title: 'PoliLoom - Verify Political Data',
  description:
    'Join the community validating political information for Wikidata. Review and confirm politician data extracted from Wikipedia and government sources to help build accurate, open political knowledge.',
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
              <ArchivedPageProvider>{children}</ArchivedPageProvider>
            </EvaluationProvider>
          </EvaluationFiltersProvider>
        </SessionProvider>
      </body>
    </html>
  )
}
