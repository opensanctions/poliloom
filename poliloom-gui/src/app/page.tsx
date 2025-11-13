'use client'

import { Header } from '@/components/Header'
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

  // Convert languages to MultiSelect options
  const languageOptions: MultiSelectOption[] = languages.map((lang) => ({
    value: lang.wikidata_id,
    label: lang.name,
  }))

  // Convert countries to MultiSelect options
  const countryOptions: MultiSelectOption[] = countries.map((country) => ({
    value: country.wikidata_id,
    label: country.name,
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
      <main className="bg-gray-50 grid place-items-center py-12 px-4 sm:px-6 lg:px-8 min-h-0 overflow-y-auto">
        <div className="max-w-2xl w-full">
          <div className="bg-white shadow rounded-lg">
            <div className="px-6 py-4 border-b border-gray-200">
              <h1 className="text-xl font-semibold text-gray-900">Filter Preferences</h1>
              <p className="mt-1 text-sm text-gray-600">
                Choose which languages and countries to filter politicians by.
              </p>
            </div>

            <div className="px-6 py-6 space-y-8">
              {preferencesError && (
                <div className="bg-red-50 border border-red-200 rounded-md p-4">
                  <p className="text-red-800 text-sm">{preferencesError}</p>
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">Languages</label>
                <p className="text-sm text-gray-500 mb-4">
                  Filter politicians based on the languages of their source documents.
                </p>
                <MultiSelect
                  options={languageOptions}
                  selected={languagePreferences}
                  onChange={handleLanguageChange}
                  placeholder="No filter - showing all"
                  loading={loadingLanguages}
                  disabled={updating}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">Countries</label>
                <p className="text-sm text-gray-500 mb-4">
                  Filter politicians based on their citizenship.
                </p>
                <MultiSelect
                  options={countryOptions}
                  selected={countryPreferences}
                  onChange={handleCountryChange}
                  placeholder="No filter - showing all"
                  loading={loadingCountries}
                  disabled={updating}
                />
              </div>
            </div>

            <div className="px-6 py-4 border-t border-gray-200 flex justify-end">
              <Anchor
                href="/evaluate"
                className="bg-indigo-600 text-white font-medium hover:bg-indigo-700 px-4 py-2 rounded-md transition-colors"
              >
                Start Evaluating
              </Anchor>
            </div>
          </div>
        </div>
      </main>
    </>
  )
}
