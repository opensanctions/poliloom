'use client'

import { useState } from 'react'
import { Header } from '@/components/Header'
import { Button } from '@/components/Button'
import { Input } from '@/components/Input'
import { Property, Politician } from '@/types'
import { PropertiesEvaluation } from '@/components/PropertiesEvaluation'
import { AddPropertyForm } from '@/components/AddPropertyForm'
import { EntitySelector } from '@/components/EntitySelector'

export default function CreatePage() {
  const [selectedPolitician, setSelectedPolitician] = useState<{
    id: string
    name: string
    wikidata_id: string
  } | null>(null)
  const [name, setName] = useState('')
  const [wikidataId, setWikidataId] = useState('')
  const [properties, setProperties] = useState<Property[]>([])

  const handleSelectPolitician = (politician: Politician) => {
    // Use the politician data directly from search results
    setSelectedPolitician({
      id: politician.id,
      name: politician.name,
      wikidata_id: politician.wikidata_id || '',
    })
    setName(politician.name)
    setWikidataId(politician.wikidata_id || '')
    setProperties(politician.properties)
  }

  const handleClearPolitician = () => {
    setSelectedPolitician(null)
    setName('')
    setWikidataId('')
    setProperties([])
  }

  const handleSubmit = () => {
    // TODO: Implement API integration
    console.log({
      politician_id: selectedPolitician?.id || null,
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

            <div>
              <div className="px-6 py-6 space-y-8">
                {/* Politician Search */}
                <div className="space-y-6">
                  <h2 className="text-lg font-medium text-gray-900">Select Politician</h2>
                  <p className="text-sm text-gray-600">
                    Optional: Search for an existing politician to load their data, or leave empty
                    to create a new one.
                  </p>

                  <EntitySelector<Politician>
                    searchEndpoint="/api/politicians"
                    placeholder="Search for politicians..."
                    selectedEntity={
                      selectedPolitician
                        ? {
                            name: selectedPolitician.name,
                            id: selectedPolitician.wikidata_id || selectedPolitician.id,
                          }
                        : null
                    }
                    onSelect={handleSelectPolitician}
                    onClear={handleClearPolitician}
                  />
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
                <div className="space-y-6">
                  <h2 className="text-lg font-medium text-gray-900">Properties</h2>

                  {/* Add Property Form */}
                  <AddPropertyForm
                    onAddProperty={(property) => {
                      setProperties([...properties, property])
                    }}
                  />

                  {/* Display existing properties */}
                  {properties.length > 0 && (
                    <div className="mt-6">
                      <PropertiesEvaluation
                        properties={properties}
                        evaluations={new Map()}
                        onAction={() => {}}
                        onShowArchived={() => {}}
                        onHover={() => {}}
                        activeArchivedPageId={null}
                      />
                    </div>
                  )}
                </div>
              </div>

              {/* Footer Actions */}
              <div className="px-6 py-4 border-t border-gray-200 flex justify-between">
                <Button type="button" variant="secondary" onClick={() => window.history.back()}>
                  Cancel
                </Button>
                <Button type="button" onClick={handleSubmit} className="px-6 py-3">
                  {selectedPolitician ? 'Update Politician' : 'Create Politician'}
                </Button>
              </div>
            </div>
          </div>
        </div>
      </main>
    </>
  )
}
