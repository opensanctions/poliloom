import { UserProvider } from '@/contexts/UserContext'
import { EvaluationSessionProvider } from '@/contexts/EvaluationSessionContext'
import { EventStreamProvider } from '@/contexts/EventStreamContext'
import { EvaluationCountProvider } from '@/contexts/EvaluationCountContext'
import { NextPoliticianProvider } from '@/contexts/NextPoliticianContext'
import { Header } from '@/components/layout/Header'
import { OmniBox } from '@/components/layout/OmniBox'
import { EvaluationCountButton } from '@/components/layout/EvaluationCountButton'
import { ThemeToggle } from '@/components/layout/ThemeToggle'
import { AuthButton } from '@/components/layout/AuthButton'
import { getUser, getEvaluationCount } from '@/lib/api-auth'

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const [user, evaluationCount] = await Promise.all([getUser(), getEvaluationCount()])

  return (
    <UserProvider initialUser={user}>
      <EventStreamProvider>
        <EvaluationSessionProvider>
          <EvaluationCountProvider initialCount={evaluationCount}>
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
    </UserProvider>
  )
}
