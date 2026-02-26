'use client'

import { useMemo } from 'react'
import { Box } from '@/components/ui/Box'
import { Button } from '@/components/ui/Button'
import { Footer } from '@/components/ui/Footer'
import { Toggle } from '@/components/ui/Toggle'
import { MultiSelect, MultiSelectOption } from '@/components/entity/MultiSelect'
import { useUserPreferences } from '@/contexts/UserPreferencesContext'
import { useUserProgress } from '@/contexts/UserProgressContext'
import { useEvaluationSession } from '@/contexts/EvaluationSessionContext'
import { useNextPoliticianContext } from '@/contexts/NextPoliticianContext'
import { PreferenceType, WikidataEntity } from '@/types'

export default function Home() {
  const {
    languages,
    countries,
    loadingLanguages,
    loadingCountries,
    updateFilters,
    isAdvancedMode,
    setAdvancedMode,
  } = useUserPreferences()
  const { hasCompletedBasicTutorial, hasCompletedAdvancedTutorial } = useUserProgress()
  const { startSession } = useEvaluationSession()
  const {
    nextHref,
    loading: loadingNext,
    enrichmentMeta,
    languageFilters,
    countryFilters,
  } = useNextPoliticianContext()

  // Determine CTA state
  const needsTutorial = !hasCompletedBasicTutorial
  const needsAdvancedTutorial = isAdvancedMode && !hasCompletedAdvancedTutorial

  const { ctaHref, ctaText, shouldStartSession } = useMemo(() => {
    if (needsTutorial) {
      return { ctaHref: '/tutorial', ctaText: 'Start Tutorial', shouldStartSession: false }
    }
    if (needsAdvancedTutorial) {
      return { ctaHref: '/tutorial', ctaText: 'Start Advanced Tutorial', shouldStartSession: false }
    }
    if (nextHref) {
      return { ctaHref: nextHref, ctaText: 'Start Your Session', shouldStartSession: true }
    }
    return { ctaHref: null, ctaText: 'Start Your Session', shouldStartSession: false }
  }, [needsTutorial, needsAdvancedTutorial, nextHref])

  const isWaitingForEnrichment = !nextHref && enrichmentMeta?.has_enrichable_politicians === true
  const isAllCaughtUp =
    !nextHref && !loadingNext && enrichmentMeta?.has_enrichable_politicians === false

  // Convert to MultiSelectOption format with counts
  const languageOptions: MultiSelectOption[] = languages.map((lang) => ({
    value: lang.wikidata_id,
    label: lang.name,
    count: lang.sources_count,
  }))

  const countryOptions: MultiSelectOption[] = countries.map((country) => ({
    value: country.wikidata_id,
    label: country.name,
    count: country.citizenships_count,
  }))

  // Generic handler for filter changes
  const createFilterHandler =
    (type: PreferenceType, allItems: WikidataEntity[]) => (qids: string[]) => {
      const items = allItems.filter((item) => qids.includes(item.wikidata_id))
      updateFilters(type, items)
    }

  const handleLanguageChange = createFilterHandler(PreferenceType.LANGUAGE, languages)
  const handleCountryChange = createFilterHandler(PreferenceType.COUNTRY, countries)

  return (
    <main className="min-h-0 overflow-y-auto flex flex-col">
      {/* Filters Section */}
      <div className="flex-1 max-w-6xl mx-auto px-6 pt-12 w-full">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-foreground mb-4">Configure Your Session</h1>
          <p className="text-lg text-foreground-tertiary">
            Pick your focus, then work through a batch of politicians at your own pace.
          </p>
        </div>

        <div className="space-y-6">
          <MultiSelect
            title="Which countries are you interested in?"
            description="We'll show you politicians with citizenship from these countries"
            icon="🌍"
            options={countryOptions}
            selected={countryFilters}
            onChange={handleCountryChange}
            loading={loadingCountries}
          />

          <MultiSelect
            title="What languages can you read?"
            description="We'll show you politicians with source documents in these languages"
            icon="🌐"
            options={languageOptions}
            selected={languageFilters}
            onChange={handleLanguageChange}
            loading={loadingLanguages}
          />
        </div>

        {/* CTA Section */}
        <Box className="mt-12 p-8">
          <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h3 className="text-lg font-semibold text-foreground mb-2">Ready to start?</h3>
              <p className="text-foreground-tertiary">
                {isAllCaughtUp
                  ? 'No more politicians to evaluate for your current filters. Try different filters to continue contributing.'
                  : isWaitingForEnrichment
                    ? "Our AI is reading Wikipedia so you don't have to. Hang tight!"
                    : languageFilters.length > 0 || countryFilters.length > 0
                      ? 'Your filters are set. Begin evaluating politicians that match your criteria.'
                      : "No filters selected. You'll evaluate politicians from all languages and countries."}
              </p>
            </div>
            <Button
              href={isWaitingForEnrichment ? '/session/enriching' : (ctaHref ?? undefined)}
              disabled={isWaitingForEnrichment ? false : !ctaHref || loadingNext}
              size="xlarge"
              className="shrink-0"
              onClick={
                isWaitingForEnrichment || shouldStartSession ? () => startSession() : undefined
              }
            >
              {ctaText}
            </Button>
          </div>

          {/* Advanced Mode Toggle */}
          <div className="mt-6 pt-6 border-t border-border-muted">
            <label className="flex items-center gap-3 text-sm text-foreground-tertiary cursor-pointer">
              <Toggle
                checked={isAdvancedMode}
                onChange={(e) => setAdvancedMode(e.target.checked)}
              />
              <span>
                Advanced mode{' '}
                <span className="text-foreground-subtle">
                  — enables deprecating existing Wikidata statements
                </span>
              </span>
            </label>
          </div>
        </Box>
      </div>

      <Footer />
    </main>
  )
}
