'use client'

import { Header } from '@/components/Header'
import { Hero } from '@/components/Hero'
import { Anchor } from '@/components/Anchor'
import { MultiSelect, MultiSelectOption } from '@/components/MultiSelect'
import { usePreferencesContext } from '@/contexts/PreferencesContext'
import { PreferenceType, WikidataEntity } from '@/types'

export default function Home() {
  const {
    preferences,
    languages,
    countries,
    loading: updating,
    loadingLanguages,
    loadingCountries,
    error: preferencesError,
    updatePreferences,
  } = usePreferencesContext()

  const languagePreferences = preferences
    .filter((p) => p.preference_type === PreferenceType.LANGUAGE)
    .map((p) => p.wikidata_id)

  const countryPreferences = preferences
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

  // Generic handler for preference changes
  const createPreferenceHandler =
    (type: PreferenceType, allItems: WikidataEntity[]) => (qids: string[]) => {
      const items = allItems.filter((item) => qids.includes(item.wikidata_id))
      updatePreferences(type, items)
    }

  const handleLanguageChange = createPreferenceHandler(PreferenceType.LANGUAGE, languages)
  const handleCountryChange = createPreferenceHandler(PreferenceType.COUNTRY, countries)

  return (
    <>
      <Header />
      <main className="bg-gray-50 min-h-0 overflow-y-auto">
        <Hero
          title="Welcome to PoliLoom"
          description={
            <>
              Help improve Wikidata by verifying politician information extracted from government
              sources and Wikipedia. Review birth dates, positions, and other details to ensure
              accuracy before they&apos;re added to the knowledge base.
            </>
          }
        >
          <p className="mt-4 text-indigo-200">
            New to PoliLoom?{' '}
            <Anchor
              href="/guide"
              className="text-white font-semibold underline hover:text-indigo-100"
            >
              Check out the guide
            </Anchor>{' '}
            to learn how reviewing works.
          </p>
        </Hero>

        {/* Filters Section */}
        <div className="max-w-6xl mx-auto px-8 py-12">
          {preferencesError && (
            <div className="bg-red-50 border-l-4 border-red-400 rounded-md p-4 mb-8">
              <p className="text-red-800 font-medium">{preferencesError}</p>
            </div>
          )}

          <div className="mb-8">
            <h2 className="text-2xl font-bold text-gray-900 mb-2">Customize Your Review Session</h2>
            <p className="text-gray-600">
              Select the languages and countries you&apos;re interested in reviewing. Leave filters
              empty to review all available politicians.
            </p>
          </div>

          <div className="space-y-6">
            <MultiSelect
              title="What languages can you read?"
              description="We'll show you politicians with source documents in these languages"
              icon="🌐"
              options={languageOptions}
              selected={languagePreferences}
              onChange={handleLanguageChange}
              loading={loadingLanguages}
              disabled={updating}
            />

            <MultiSelect
              title="Which countries are you interested in?"
              description="We'll show you politicians with citizenship from these countries"
              icon="🌍"
              options={countryOptions}
              selected={countryPreferences}
              onChange={handleCountryChange}
              loading={loadingCountries}
              disabled={updating}
            />
          </div>

          {/* CTA Section */}
          <div className="mt-12 bg-white rounded-lg shadow-sm border border-gray-200 p-8">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Ready to start?</h3>
                <p className="text-gray-600">
                  {languagePreferences.length > 0 || countryPreferences.length > 0
                    ? 'Your filters are set. Begin reviewing politicians that match your criteria.'
                    : "No filters selected. You'll review politicians from all languages and countries."}
                </p>
              </div>
              <Anchor
                href="/evaluate"
                className="bg-indigo-600 text-white font-semibold hover:bg-indigo-700 px-8 py-4 rounded-lg transition-colors shadow-sm hover:shadow-md whitespace-nowrap ml-6"
              >
                Begin Review Session
              </Anchor>
            </div>
          </div>
        </div>
      </main>
    </>
  )
}
