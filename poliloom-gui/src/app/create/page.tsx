'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Footer } from '@/components/ui/Footer'
import { HeaderedBox } from '@/components/ui/HeaderedBox'
import { Property, Politician } from '@/types'
import { PropertiesEvaluation } from '@/components/evaluation/PropertiesEvaluation'
import { AddPropertyForm } from '@/components/entity/AddPropertyForm'
import { EntitySelector } from '@/components/entity/EntitySelector'

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
    // Ensure backend properties have both key and id set (key = id)
    const propertiesWithKeys = politician.properties.map((prop) => ({
      ...prop,
      key: prop.id || prop.key,
    }))
    setProperties(propertiesWithKeys)

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

  const handleEvaluate = (propertyId: string, action: 'accept' | 'reject') => {
    setEvaluations((prev) => {
      const newMap = new Map(prev)
      const currentValue = newMap.get(propertyId)
      const targetValue = action === 'accept'

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

  const handleSubmit = async () => {
    if (!selectedPolitician) return

    // Filter properties for submission
    const manualProps = properties.filter((p) => !p.id && evaluations.get(p.key) === true)
    const extractedPropsToEvaluate = properties.filter((p) => p.id && evaluations.has(p.key))

    // Validate that there's something to submit
    if (manualProps.length === 0 && extractedPropsToEvaluate.length === 0) {
      alert('Please add at least one property or evaluate existing properties')
      return
    }

    const [submittingMessage, successMessage] = selectedPolitician.id
      ? ['Updating...', `Successfully updated ${selectedPolitician.name}`]
      : ['Creating...', `Successfully created ${selectedPolitician.name}`]

    // Show submitting state
    const submitButton = document.querySelector('button[type="button"]:last-of-type')
    if (submitButton) {
      submitButton.textContent = submittingMessage
      ;(submitButton as HTMLButtonElement).disabled = true
    }

    try {
      const errors: string[] = []

      // For NEW politicians: create with manually added properties
      if (!selectedPolitician.id) {
        const propertyPayload = manualProps.map((p) => ({
          type: p.type,
          value: p.value,
          value_precision: p.value_precision,
          entity_id: p.entity_id,
          qualifiers_json: p.qualifiers,
          references_json: p.references,
        }))

        const response = await fetch('/api/politicians', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            politicians: [
              {
                name: selectedPolitician.name,
                properties: propertyPayload,
              },
            ],
          }),
        })

        if (!response.ok) {
          throw new Error(`Failed to create politician: ${response.statusText}`)
        }

        const result = await response.json()
        if (!result.success) {
          errors.push(...(result.errors || ['Failed to create politician']))
        }
      }
      // For EXISTING politicians: add properties and/or submit evaluations
      else {
        const requests: Promise<Response>[] = []

        // Add manually added properties
        if (manualProps.length > 0) {
          const propertyPayload = manualProps.map((p) => ({
            type: p.type,
            value: p.value,
            value_precision: p.value_precision,
            entity_id: p.entity_id,
            qualifiers_json: p.qualifiers,
            references_json: p.references,
          }))

          requests.push(
            fetch(`/api/politicians/${selectedPolitician.id}/properties`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ properties: propertyPayload }),
            }),
          )
        }

        // Submit evaluations for extracted properties
        if (extractedPropsToEvaluate.length > 0) {
          const evaluationPayload = extractedPropsToEvaluate.map((p) => ({
            id: p.id!,
            is_confirmed: evaluations.get(p.key)!,
          }))

          requests.push(
            fetch('/api/evaluations', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ evaluations: evaluationPayload }),
            }),
          )
        }

        // Execute requests in parallel
        const responses = await Promise.all(requests)

        // Check all responses
        for (const response of responses) {
          if (!response.ok) {
            throw new Error(`Failed to submit: ${response.statusText}`)
          }
          const result = await response.json()
          if (!result.success) {
            errors.push(...(result.errors || ['Operation failed']))
          }
        }
      }

      // Handle errors or success
      if (errors.length > 0) {
        alert(`Errors occurred:\n${errors.join('\n')}`)
      } else {
        alert(successMessage)
        // Clear form state
        setSelectedPolitician(null)
        setProperties([])
        setEvaluations(new Map())
      }
    } catch (error) {
      console.error('Error submitting:', error)
      alert(`Error submitting: ${error instanceof Error ? error.message : 'Unknown error'}`)
    } finally {
      // Restore button state
      if (submitButton) {
        submitButton.textContent = selectedPolitician.id ? 'Update Politician' : 'Create Politician'
        ;(submitButton as HTMLButtonElement).disabled = false
      }
    }
  }

  return (
    <main className="min-h-0 overflow-y-auto flex flex-col">
      <div className="flex-1 max-w-6xl mx-auto px-6 pt-12 w-full">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-foreground mb-4">Add Politician Data</h1>
          <p className="text-lg text-foreground-tertiary">
            Search for an existing politician to edit, or create a new one from scratch.
          </p>
        </div>

        <HeaderedBox
          title="Politician Details"
          description="Search or create a politician and add their properties"
          icon="👤"
        >
          <div className="space-y-8">
            {/* Politician Search/Create */}
            <EntitySelector<Politician>
              searchEndpoint="/api/politicians/search"
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

            {/* Properties - only show when a politician is selected */}
            {selectedPolitician && (
              <div className="space-y-6">
                <h2 className="text-lg font-medium text-foreground">Properties</h2>

                {/* Add Property Form */}
                <AddPropertyForm
                  onAddProperty={(property) => {
                    setProperties([...properties, property])
                    // Auto-confirm newly added properties since user is manually adding them
                    setEvaluations((prev) => {
                      const newMap = new Map(prev)
                      newMap.set(property.key, true)
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

                {/* Actions */}
                <div className="pt-4 border-t border-border-muted flex justify-between">
                  <Button type="button" variant="secondary" onClick={() => window.history.back()}>
                    Cancel
                  </Button>
                  <Button type="button" onClick={handleSubmit} size="large">
                    {selectedPolitician.id ? 'Update Politician' : 'Create Politician'}
                  </Button>
                </div>
              </div>
            )}
          </div>
        </HeaderedBox>
      </div>

      <Footer />
    </main>
  )
}
