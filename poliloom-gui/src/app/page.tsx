'use client'

import { Header } from '@/components/layout/Header'
import { Button } from '@/components/ui/Button'
import { Toggle } from '@/components/ui/Toggle'
import { MultiSelect, MultiSelectOption } from '@/components/entity/MultiSelect'
import { useUserPreferences } from '@/contexts/UserPreferencesContext'
import { useTutorial } from '@/contexts/TutorialContext'
import { useMemo } from 'react'
import { PreferenceType, WikidataEntity } from '@/types'

export default function Home() {
  const {
    filters,
    languages,
    countries,
    loadingLanguages,
    loadingCountries,
    updateFilters,
    isAdvancedMode,
    setAdvancedMode,
  } = useUserPreferences()
  const { hasCompletedBasicTutorial, hasCompletedAdvancedTutorial } = useTutorial()

  // Determine where to route the user based on tutorial completion and advanced mode
  const { ctaHref, ctaText } = useMemo(() => {
    if (!hasCompletedBasicTutorial) {
      return { ctaHref: '/tutorial', ctaText: 'Start Tutorial' }
    }
    if (isAdvancedMode && !hasCompletedAdvancedTutorial) {
      return { ctaHref: '/tutorial', ctaText: 'Start Advanced Tutorial' }
    }
    return { ctaHref: '/evaluate', ctaText: 'Start Your Session' }
  }, [hasCompletedBasicTutorial, hasCompletedAdvancedTutorial, isAdvancedMode])

  const languageFilters = filters
    .filter((p) => p.preference_type === PreferenceType.LANGUAGE)
    .map((p) => p.wikidata_id)

  const countryFilters = filters
    .filter((p) => p.preference_type === PreferenceType.COUNTRY)
    .map((p) => p.wikidata_id)

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
    <>
      <Header />
      <main className="bg-gray-50 min-h-0 overflow-y-auto">
        {/* Filters Section */}
        <div className="max-w-6xl mx-auto px-8 py-12">
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-gray-900 mb-4">Configure Your Session</h1>
            <p className="text-lg text-gray-600">
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
          <div className="mt-12 bg-white rounded-lg shadow-sm border border-gray-200 p-8">
            <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Ready to start?</h3>
                <p className="text-gray-600">
                  {languageFilters.length > 0 || countryFilters.length > 0
                    ? 'Your filters are set. Begin evaluating politicians that match your criteria.'
                    : "No filters selected. You'll evaluate politicians from all languages and countries."}
                </p>
              </div>
              <Button href={ctaHref} size="xlarge" className="shrink-0">
                {ctaText}
              </Button>
            </div>

            {/* Advanced Mode Toggle */}
            <div className="mt-6 pt-6 border-t border-gray-100">
              <label className="flex items-center gap-3 text-sm text-gray-600 cursor-pointer">
                <Toggle
                  checked={isAdvancedMode}
                  onChange={(e) => setAdvancedMode(e.target.checked)}
                />
                <span>
                  Advanced mode{' '}
                  <span className="text-gray-400">
                    — enables deprecating existing Wikidata statements
                  </span>
                </span>
              </label>
            </div>
          </div>
        </div>
      </main>
    </>
  )
}
