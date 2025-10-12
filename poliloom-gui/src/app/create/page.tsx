'use client'

import { useState, useEffect, useRef } from 'react'
import { Header } from '@/components/Header'
import { Button } from '@/components/Button'
import { Input } from '@/components/Input'
import { Property, PropertyType, Politician } from '@/types'
import { PropertiesForm } from '@/components/PropertiesForm'

export default function CreatePage() {
  const [selectedPoliticianId, setSelectedPoliticianId] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [wikidataId, setWikidataId] = useState('')
  const [properties, setProperties] = useState<Property[]>([])

  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<Politician[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [showDropdown, setShowDropdown] = useState(false)
  const searchTimeoutRef = useRef<NodeJS.Timeout | undefined>(undefined)

  // Debounced search effect
  useEffect(() => {
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current)
    }

    if (!searchQuery.trim()) {
      setSearchResults([])
      setShowDropdown(false)
      setIsSearching(false)
      return
    }

    searchTimeoutRef.current = setTimeout(async () => {
      setIsSearching(true)
      try {
        const response = await fetch(
          `/api/politicians?search=${encodeURIComponent(searchQuery)}&limit=10`,
        )
        if (response.ok) {
          const results = await response.json()
          setSearchResults(results)
          setShowDropdown(results.length > 0)
        }
      } catch (error) {
        console.error('Search failed:', error)
      } finally {
        setIsSearching(false)
      }
    }, 300)

    return () => {
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current)
      }
    }
  }, [searchQuery])

  const handleSelectPolitician = (politician: Politician) => {
    setShowDropdown(false)
    setSearchQuery('')
    setSearchResults([])

    // Use the politician data directly from search results
    setSelectedPoliticianId(politician.id)
    setName(politician.name)
    setWikidataId(politician.wikidata_id || '')
    setProperties(politician.properties)
  }

  const handleClearPolitician = () => {
    setSelectedPoliticianId(null)
    setName('')
    setWikidataId('')
    setProperties([])
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    // TODO: Implement API integration
    console.log({
      politician_id: selectedPoliticianId,
      name,
      wikidata_id: wikidataId || null,
      properties,
    })
  }

  return (
    <>
      <Header />
      <main className="bg-gray-50 py-12 px-4 sm:px-6 lg:px-8 min-h-0 overflow-y-auto">
        <div className="max-w-4xl mx-auto">
          <div className="bg-white shadow rounded-lg">
            <div className="px-6 py-4 border-b border-gray-200">
              <h1 className="text-xl font-semibold text-gray-900">Add Politician Data</h1>
              <p className="mt-1 text-sm text-gray-600">
                Search for an existing politician to edit, or create a new one from scratch.
              </p>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="px-6 py-6 space-y-8">
                {/* Politician Search */}
                <div className="space-y-6">
                  <h2 className="text-lg font-medium text-gray-900">Select Politician</h2>
                  <p className="text-sm text-gray-600">
                    Optional: Search for an existing politician to load their data, or leave empty
                    to create a new one.
                  </p>

                  <div className="relative">
                    <Input
                      type="text"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      placeholder="Search for politicians..."
                      disabled={selectedPoliticianId !== null}
                    />
                    {isSearching && (
                      <div className="absolute right-3 top-1/2 -translate-y-1/2">
                        <div className="animate-spin h-4 w-4 border-2 border-indigo-600 border-t-transparent rounded-full" />
                      </div>
                    )}

                    {/* Dropdown */}
                    {showDropdown && (
                      <div className="absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-auto">
                        {searchResults.length > 0 ? (
                          <ul>
                            {searchResults.map((result) => (
                              <li key={result.id}>
                                <button
                                  type="button"
                                  onClick={() => handleSelectPolitician(result)}
                                  className="w-full px-4 py-3 text-left hover:bg-gray-50 focus:bg-gray-50 focus:outline-none"
                                >
                                  <div className="font-medium text-gray-900">{result.name}</div>
                                  <div className="text-sm text-gray-500">
                                    {result.wikidata_id && `(${result.wikidata_id})`}
                                  </div>
                                </button>
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <div className="px-4 py-3 text-sm text-gray-500">No results found</div>
                        )}
                      </div>
                    )}
                  </div>

                  {selectedPoliticianId && (
                    <div className="p-4 bg-blue-50 border border-blue-200 rounded-md flex justify-between items-center">
                      <div>
                        <p className="text-sm font-medium text-blue-900">
                          Editing: {name} {wikidataId && `(${wikidataId})`}
                        </p>
                        <p className="text-xs text-blue-700 mt-1">
                          You are editing an existing politician&apos;s data
                        </p>
                      </div>
                      <Button
                        type="button"
                        variant="secondary"
                        onClick={handleClearPolitician}
                        className="text-sm"
                      >
                        Clear
                      </Button>
                    </div>
                  )}
                </div>

                {/* Basic Information */}
                <div className="space-y-6">
                  <h2 className="text-lg font-medium text-gray-900">Basic Information</h2>

                  <Input
                    type="text"
                    id="name"
                    label="Name"
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g., Jane Doe"
                  />

                  <Input
                    type="text"
                    id="wikidataId"
                    label="Wikidata ID"
                    value={wikidataId}
                    onChange={(e) => setWikidataId(e.target.value)}
                    placeholder="e.g., Q12345"
                  />
                </div>

                {/* Properties */}
                <PropertiesForm properties={properties} onPropertiesChange={setProperties} />
              </div>

              {/* Footer Actions */}
              <div className="px-6 py-4 border-t border-gray-200 flex justify-between">
                <Button type="button" variant="secondary" onClick={() => window.history.back()}>
                  Cancel
                </Button>
                <Button type="submit" className="px-6 py-3">
                  {selectedPoliticianId ? 'Update Politician' : 'Create Politician'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      </main>
    </>
  )
}
