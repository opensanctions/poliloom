'use client'

import { Header } from '@/components/layout/Header'
import { Hero } from '@/components/layout/Hero'
import { Anchor } from '@/components/ui/Anchor'
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
    return { ctaHref: '/evaluate', ctaText: 'Begin Review Session' }
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
        <Hero
          title="Welcome to PoliLoom"
          description={
            <>
              Help build the world&apos;s largest open database of politicians. Review facts
              extracted from government sources and Wikipedia to ensure accuracy before they&apos;re
              published.
              <br />
              <br />
              Your contributions make political data freely accessible to everyone.
            </>
          }
        />

        {/* Filters Section */}
        <div className="max-w-6xl mx-auto px-8 py-12">
          <div className="mb-8">
            <h2 className="text-2xl font-bold text-gray-900 mb-2">Customize Your Review Session</h2>
            <p className="text-gray-600">
              Select the countries and languages you&apos;re interested in reviewing. Leave filters
              empty to review all available politicians.
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
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Ready to start?</h3>
                <p className="text-gray-600">
                  {languageFilters.length > 0 || countryFilters.length > 0
                    ? 'Your filters are set. Begin reviewing politicians that match your criteria.'
                    : "No filters selected. You'll review politicians from all languages and countries."}
                </p>
              </div>
              <Anchor
                href={ctaHref}
                className="bg-indigo-600 text-white font-semibold hover:bg-indigo-700 px-8 py-4 rounded-lg transition-colors shadow-sm hover:shadow-md whitespace-nowrap ml-6"
              >
                {ctaText}
              </Anchor>
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
