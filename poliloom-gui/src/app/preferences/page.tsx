"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { Header } from "@/components/Header"
import { MultiSelect, MultiSelectOption } from "@/components/MultiSelect"
import { usePreferencesContext } from "@/contexts/PreferencesContext"
import { LanguageResponse, CountryResponse } from "@/types"

export default function PreferencesPage() {
  const router = useRouter()
  const {
    languagePreferences,
    countryPreferences,
    loading: updating,
    error: preferencesError,
    updateLanguagePreferences,
    updateCountryPreferences
  } = usePreferencesContext()

  const [languages, setLanguages] = useState<LanguageResponse[]>([])
  const [loadingLanguages, setLoadingLanguages] = useState(true)
  const [countries, setCountries] = useState<CountryResponse[]>([])
  const [loadingCountries, setLoadingCountries] = useState(true)
  const [error, setError] = useState<string | null>(null)




  // Fetch available languages
  useEffect(() => {
    const fetchLanguages = async () => {
      try {
        const response = await fetch('/api/languages')
        if (!response.ok) {
          throw new Error(`Failed to fetch languages: ${response.statusText}`)
        }
        const data: LanguageResponse[] = await response.json()
        setLanguages(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch languages')
        console.error('Error fetching languages:', err)
      } finally {
        setLoadingLanguages(false)
      }
    }

    fetchLanguages()
  }, [])

  // Fetch available countries
  useEffect(() => {
    const fetchCountries = async () => {
      try {
        const response = await fetch('/api/countries')
        if (!response.ok) {
          throw new Error(`Failed to fetch countries: ${response.statusText}`)
        }
        const data: CountryResponse[] = await response.json()
        setCountries(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch countries')
        console.error('Error fetching countries:', err)
      } finally {
        setLoadingCountries(false)
      }
    }

    fetchCountries()
  }, [])


  // Convert languages to MultiSelect options
  const languageOptions: MultiSelectOption[] = languages.map(lang => ({
    value: lang.wikidata_id,
    label: lang.name
  }))

  // Convert countries to MultiSelect options
  const countryOptions: MultiSelectOption[] = countries.map(country => ({
    value: country.wikidata_id,
    label: country.name
  }))

  const displayError = error || preferencesError

  return (
    <>
      <Header />
      <main className="bg-gray-50 grid place-items-center py-12 px-4 sm:px-6 lg:px-8 min-h-0 overflow-y-auto">
        <div className="max-w-2xl w-full">
          <div className="bg-white shadow rounded-lg">
            <div className="px-6 py-4 border-b border-gray-200">
              <h1 className="text-xl font-semibold text-gray-900">
                Filter Preferences
              </h1>
              <p className="mt-1 text-sm text-gray-600">
                Choose which languages and countries to filter politicians by.
              </p>
            </div>

            <div className="px-6 py-6 space-y-8">
              {displayError && (
                <div className="bg-red-50 border border-red-200 rounded-md p-4">
                  <p className="text-red-800 text-sm">{displayError}</p>
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">
                  Languages
                </label>
                <p className="text-sm text-gray-500 mb-4">
                  Filter politicians based on the languages of their source documents.
                </p>
                <MultiSelect
                  options={languageOptions}
                  selected={languagePreferences}
                  onChange={updateLanguagePreferences}
                  placeholder="Select languages..."
                  loading={loadingLanguages}
                  disabled={updating}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">
                  Countries
                </label>
                <p className="text-sm text-gray-500 mb-4">
                  Filter politicians based on their citizenship.
                </p>
                <MultiSelect
                  options={countryOptions}
                  selected={countryPreferences}
                  onChange={updateCountryPreferences}
                  placeholder="Select countries..."
                  loading={loadingCountries}
                  disabled={updating}
                />
              </div>

            </div>

            <div className="px-6 py-4 border-t border-gray-200 flex justify-end">
              <button
                onClick={() => router.push('/')}
                className="px-4 py-2 bg-indigo-600 text-white font-medium rounded-md hover:bg-indigo-700"
              >
                Start Evaluating
              </button>
            </div>
          </div>
        </div>
      </main>
    </>
  )
}