import { UserPreferencesProvider } from '@/contexts/UserPreferencesContext'
import { EvaluationSessionProvider } from '@/contexts/EvaluationSessionContext'
import { UserProgressProvider } from '@/contexts/UserProgressContext'
import { EvaluationCountProvider } from '@/contexts/EvaluationCountContext'
import { NextPoliticianProvider } from '@/contexts/NextPoliticianContext'
import { Header } from '@/components/layout/Header'
import { HeaderSearch } from '@/components/layout/HeaderSearch'
import { EvaluationCountButton } from '@/components/layout/EvaluationCountButton'
import { ThemeToggle } from '@/components/layout/ThemeToggle'
import { AuthButton } from '@/components/layout/AuthButton'

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <UserPreferencesProvider>
      <EvaluationSessionProvider>
        <UserProgressProvider>
          <EvaluationCountProvider>
            <NextPoliticianProvider>
              <Header
                left={<HeaderSearch />}
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
        </UserProgressProvider>
      </EvaluationSessionProvider>
    </UserPreferencesProvider>
  )
}
