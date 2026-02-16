import { UserPreferencesProvider } from '@/contexts/UserPreferencesContext'
import { EvaluationSessionProvider } from '@/contexts/EvaluationSessionContext'
import { UserProgressProvider } from '@/contexts/UserProgressContext'
import { EvaluationCountProvider } from '@/contexts/EvaluationCountContext'
import { Header } from '@/components/layout/Header'
import { EvaluationCountButton } from '@/components/layout/EvaluationCountButton'
import { ThemeToggle } from '@/components/layout/ThemeToggle'
import { AuthButton } from '@/components/layout/AuthButton'

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <UserPreferencesProvider>
      <EvaluationSessionProvider>
        <UserProgressProvider>
          <EvaluationCountProvider>
            <Header>
              <EvaluationCountButton />
              <ThemeToggle />
              <AuthButton />
            </Header>
            {children}
          </EvaluationCountProvider>
        </UserProgressProvider>
      </EvaluationSessionProvider>
    </UserPreferencesProvider>
  )
}
