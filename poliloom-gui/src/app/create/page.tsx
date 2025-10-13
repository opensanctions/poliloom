'use client'

import { useState } from 'react'
import { Header } from '@/components/Header'
import { Button } from '@/components/Button'
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
  const [properties, setProperties] = useState<Property[]>([])
  const [evaluations, setEvaluations] = useState<Map<string, boolean>>(new Map())

  const handleSelectPolitician = (politician: Politician) => {
    // Use the politician data directly from search results
    setSelectedPolitician({
      id: politician.id,
      name: politician.name,
      wikidata_id: politician.wikidata_id || '',
    })
    setProperties(politician.properties)

    // Initialize evaluations for existing properties (default to no evaluation)
    setEvaluations(new Map())
  }

  const handleCreateNew = (name: string) => {
    // Create a new politician with the entered name
    setSelectedPolitician({
      id: '',
      name: name,
      wikidata_id: '',
    })
    setProperties([])
    setEvaluations(new Map())
  }

  const handleClearPolitician = () => {
    setSelectedPolitician(null)
    setProperties([])
    setEvaluations(new Map())
  }

  const handleEvaluate = (propertyId: string, action: 'confirm' | 'discard') => {
    setEvaluations((prev) => {
      const newMap = new Map(prev)
      const currentValue = newMap.get(propertyId)
      const targetValue = action === 'confirm'

      if (currentValue === targetValue) {
        // Toggle off - remove from map
        newMap.delete(propertyId)
      } else {
        // Set new value
        newMap.set(propertyId, targetValue)
      }
      return newMap
    })
  }

  const handleSubmit = () => {
    // TODO: Implement API integration
    // Will need to submit both properties and evaluations
    console.log('Properties:', properties)
    console.log('Evaluations:', Array.from(evaluations.entries()))
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
                {/* Politician Search/Create */}
                <div className="space-y-6">
                  <EntitySelector<Politician>
                    searchEndpoint="/api/politicians"
                    placeholder="Search for politicians or enter a new name..."
                    selectedEntity={
                      selectedPolitician
                        ? {
                            name: selectedPolitician.name,
                            id: selectedPolitician.wikidata_id || 'new',
                          }
                        : null
                    }
                    onSelect={handleSelectPolitician}
                    onClear={handleClearPolitician}
                    allowCreate={true}
                    onCreateNew={handleCreateNew}
                  />
                </div>

                {/* Properties - only show when a politician is selected */}
                {selectedPolitician && (
                  <div className="space-y-6">
                    <h2 className="text-lg font-medium text-gray-900">Properties</h2>

                    {/* Add Property Form */}
                    <AddPropertyForm
                      onAddProperty={(property) => {
                        setProperties([...properties, property])
                        // Auto-confirm newly added properties since user is manually adding them
                        setEvaluations((prev) => {
                          const newMap = new Map(prev)
                          newMap.set(property.id, true)
                          return newMap
                        })
                      }}
                    />

                    {/* Display existing properties */}
                    {properties.length > 0 && (
                      <div className="mt-6">
                        <PropertiesEvaluation
                          properties={properties}
                          evaluations={evaluations}
                          onAction={handleEvaluate}
                          onShowArchived={() => {}}
                          onHover={() => {}}
                          activeArchivedPageId={null}
                        />
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Footer Actions */}
              {selectedPolitician && (
                <div className="px-6 py-4 border-t border-gray-200 flex justify-between">
                  <Button type="button" variant="secondary" onClick={() => window.history.back()}>
                    Cancel
                  </Button>
                  <Button type="button" onClick={handleSubmit} className="px-6 py-3">
                    {selectedPolitician.id ? 'Update Politician' : 'Create Politician'}
                  </Button>
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </>
  )
}
