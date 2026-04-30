import { UserProvider } from '@/contexts/UserContext'
import { EntityCatalogProvider } from '@/contexts/EntityCatalogContext'
import { EvaluationSessionProvider } from '@/contexts/EvaluationSessionContext'
import { EventStreamProvider } from '@/contexts/EventStreamContext'
import { EvaluationCountProvider } from '@/contexts/EvaluationCountContext'
import { NextPoliticianProvider } from '@/contexts/NextPoliticianContext'
import { FirstLoginAutoDetect } from '@/components/system/FirstLoginAutoDetect'
import { Header } from '@/components/layout/Header'
import { OmniBox } from '@/components/layout/OmniBox'
import { EvaluationCountButton } from '@/components/layout/EvaluationCountButton'
import { ThemeToggle } from '@/components/layout/ThemeToggle'
import { AuthButton } from '@/components/layout/AuthButton'

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <UserProvider>
      <EntityCatalogProvider>
        <FirstLoginAutoDetect />
        <EventStreamProvider>
          <EvaluationSessionProvider>
            <EvaluationCountProvider>
              <NextPoliticianProvider>
                <Header
                  left={<OmniBox />}
                  right={
                    <>
                      <EvaluationCountButton />
                      <ThemeToggle />
                      <AuthButton />
                    </>
                  }
                />
                {children}
              </NextPoliticianProvider>
            </EvaluationCountProvider>
          </EvaluationSessionProvider>
        </EventStreamProvider>
      </EntityCatalogProvider>
    </UserProvider>
  )
}
