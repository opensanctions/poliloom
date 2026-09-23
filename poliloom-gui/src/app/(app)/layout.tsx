import { SettingsProvider } from '@/contexts/SettingsContext'
import { EventStreamProvider } from '@/contexts/EventStreamContext'
import { DecisionCountProvider } from '@/contexts/DecisionCountContext'
import { NextPoliticianProvider } from '@/contexts/NextPoliticianContext'
import { FilterProvider } from '@/contexts/FilterContext'
import { Header } from '@/components/layout/Header'
import { SearchBox } from '@/components/layout/SearchBox'
import { DecisionCountButton } from '@/components/layout/DecisionCountButton'
import { ThemeToggle } from '@/components/layout/ThemeToggle'
import { AuthButton } from '@/components/layout/AuthButton'
import { getSettings, getDecisionCount } from '@/lib/api-auth'
import { resolveLanguageQids, getFilterCountryQids } from '@/lib/filters'

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const [settings, decisionCount, initialLanguageQids, initialCountryQids] = await Promise.all([
    getSettings(),
    getDecisionCount(),
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
          <DecisionCountProvider initialCount={decisionCount}>
            <NextPoliticianProvider>
              <Header
                left={<SearchBox />}
                right={
                  <>
                    <DecisionCountButton />
                    <ThemeToggle />
                    <AuthButton />
                  </>
                }
              />
              {children}
            </NextPoliticianProvider>
          </DecisionCountProvider>
        </EventStreamProvider>
      </FilterProvider>
    </SettingsProvider>
  )
}
