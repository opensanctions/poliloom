import type { Metadata } from 'next'
import './globals.css'
import { SessionProvider } from '@/components/SessionProvider'
import { ArchivedPageProvider } from '@/contexts/ArchivedPageContext'
import { PreferencesProvider } from '@/contexts/PreferencesContext'
import { PoliticiansProvider } from '@/contexts/PoliticiansContext'
import { FetchInterceptor } from '@/components/FetchInterceptor'

export const metadata: Metadata = {
  title: 'PoliLoom - Data Confirmation',
  description: 'Confirm politician data extracted from Wikipedia',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <body className="font-sans antialiased grid grid-rows-[auto_1fr] h-screen">
        <SessionProvider>
          <FetchInterceptor />
          <PreferencesProvider>
            <PoliticiansProvider>
              <ArchivedPageProvider>{children}</ArchivedPageProvider>
            </PoliticiansProvider>
          </PreferencesProvider>
        </SessionProvider>
      </body>
    </html>
  )
}
