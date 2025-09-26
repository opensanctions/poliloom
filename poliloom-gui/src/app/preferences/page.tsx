"use client"

import { useState, useEffect } from "react"
import { Header } from "@/components/Header"
import { MultiSelect, MultiSelectOption } from "@/components/MultiSelect"
import { LanguageResponse } from "@/types"

export default function PreferencesPage() {
  const [languages, setLanguages] = useState<LanguageResponse[]>([])
  const [selectedLanguages, setSelectedLanguages] = useState<string[]>([])
  const [loadingLanguages, setLoadingLanguages] = useState(true)
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

  // Convert languages to MultiSelect options
  const languageOptions: MultiSelectOption[] = languages.map(lang => ({
    value: lang.wikidata_id,
    label: lang.name
  }))

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
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">
                  Languages
                </label>
                <p className="text-sm text-gray-500 mb-4">
                  Filter politicians based on the languages of their source documents.
                </p>
                {error ? (
                  <div className="bg-red-50 border border-red-200 rounded-md p-4">
                    <p className="text-red-800 text-sm">{error}</p>
                  </div>
                ) : (
                  <MultiSelect
                    options={languageOptions}
                    selected={selectedLanguages}
                    onChange={setSelectedLanguages}
                    placeholder="Select languages..."
                    loading={loadingLanguages}
                  />
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">
                  Countries
                </label>
                <p className="text-sm text-gray-500 mb-4">
                  Filter politicians based on their citizenship.
                </p>
                <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center text-gray-500">
                  Country multiselect component coming later...
                </div>
              </div>

              <div className="flex justify-end space-x-3 pt-6 border-t border-gray-200">
                <button
                  type="button"
                  className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                >
                  Save Preferences
                </button>
              </div>
            </div>
          </div>
        </div>
      </main>
    </>
  )
}