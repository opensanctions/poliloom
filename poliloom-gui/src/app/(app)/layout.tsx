import { SettingsProvider } from '@/contexts/SettingsContext'
import { EventStreamProvider } from '@/contexts/EventStreamContext'
import { EvaluationCountProvider } from '@/contexts/EvaluationCountContext'
import { NextPoliticianProvider } from '@/contexts/NextPoliticianContext'
import { FilterProvider } from '@/contexts/FilterContext'
import { Header } from '@/components/layout/Header'
import { OmniBox } from '@/components/layout/OmniBox'
import { EvaluationCountButton } from '@/components/layout/EvaluationCountButton'
import { ThemeToggle } from '@/components/layout/ThemeToggle'
import { AuthButton } from '@/components/layout/AuthButton'
import { getSettings, getEvaluationCount } from '@/lib/api-auth'
import { resolveLanguageQids, getFilterCountryQids } from '@/lib/filters'

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const [settings, evaluationCount, initialLanguageQids, initialCountryQids] = await Promise.all([
    getSettings(),
    getEvaluationCount(),
    resolveLanguageQids(),
    getFilterCountryQids(),
  ])

  return (
    <SettingsProvider initialSettings={settings}>
      <FilterProvider
        initialLanguageQids={initialLanguageQids}
        initialCountryQids={initialCountryQids}
      >
        <EventStreamProvider>
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
        </EventStreamProvider>
      </FilterProvider>
    </SettingsProvider>
  )
}
