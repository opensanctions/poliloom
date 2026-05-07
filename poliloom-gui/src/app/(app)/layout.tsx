import { headers } from 'next/headers'
import { SettingsProvider } from '@/contexts/SettingsContext'
import { EvaluationSessionProvider } from '@/contexts/EvaluationSessionContext'
import { EventStreamProvider } from '@/contexts/EventStreamContext'
import { EvaluationCountProvider } from '@/contexts/EvaluationCountContext'
import { NextPoliticianProvider } from '@/contexts/NextPoliticianContext'
import { FilterProvider } from '@/contexts/FilterContext'
import { Header } from '@/components/layout/Header'
import { OmniBox } from '@/components/layout/OmniBox'
import { EvaluationCountButton } from '@/components/layout/EvaluationCountButton'
import { ThemeToggle } from '@/components/layout/ThemeToggle'
import { AuthButton } from '@/components/layout/AuthButton'
import { getSettings, getEvaluationCount, getLanguages } from '@/lib/api-auth'
import { getFilterLanguageQids, getFilterCountryQids } from '@/lib/filters'
import { detectAcceptLanguage } from '@/lib/detectAcceptLanguage'

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const [
    settings,
    evaluationCount,
    languages,
    sanitizedLanguageQids,
    initialCountryQids,
    headerStore,
  ] = await Promise.all([
    getSettings(),
    getEvaluationCount(),
    getLanguages(),
    getFilterLanguageQids(),
    getFilterCountryQids(),
    headers(),
  ])

  // Language autodetect: when no cookie is set we re-detect from Accept-Language
  // on every request. The first time the user touches the filter (including
  // clearing it to []), the cookie gets written and detection stops.
  const initialLanguageQids =
    sanitizedLanguageQids ?? detectAcceptLanguage(headerStore.get('accept-language'), languages)

  return (
    <SettingsProvider initialSettings={settings}>
      <FilterProvider
        initialLanguageQids={initialLanguageQids}
        initialCountryQids={initialCountryQids}
      >
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
      </FilterProvider>
    </SettingsProvider>
  )
}
