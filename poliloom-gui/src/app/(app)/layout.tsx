import { cookies, headers } from 'next/headers'
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
import {
  FILTER_COUNTRIES_COOKIE,
  FILTER_LANGUAGES_COOKIE,
  deserializeFilterCookieValue,
} from '@/lib/cookies'
import { detectAcceptLanguage } from '@/lib/detectAcceptLanguage'

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const [settings, evaluationCount, languages, cookieStore, headerStore] = await Promise.all([
    getSettings(),
    getEvaluationCount(),
    getLanguages(),
    cookies(),
    headers(),
  ])

  // Language autodetect: when no cookie is set we re-detect from Accept-Language
  // on every request. The first time the user touches the filter (including
  // clearing it to []), the cookie gets written and detection stops.
  const langCookie = cookieStore.get(FILTER_LANGUAGES_COOKIE)?.value
  const initialLanguageQids =
    langCookie !== undefined
      ? deserializeFilterCookieValue(langCookie)
      : detectAcceptLanguage(headerStore.get('accept-language'), languages)
  const initialCountryQids = deserializeFilterCookieValue(
    cookieStore.get(FILTER_COUNTRIES_COOKIE)?.value,
  )

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
