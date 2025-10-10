'use client'

import { useState } from 'react'
import { Header } from '@/components/Header'
import { EntitySelector, EntityItem } from '@/components/EntitySelector'
import { Input } from '@/components/Input'
import { Property, PropertyType } from '@/types'

export default function CreatePage() {
  const [name, setName] = useState('')
  const [wikidataId, setWikidataId] = useState('')
  const [birthDate, setBirthDate] = useState('')
  const [birthDatePrecision, setBirthDatePrecision] = useState<number>(11)
  const [deathDate, setDeathDate] = useState('')
  const [deathDatePrecision, setDeathDatePrecision] = useState<number>(11)

  const [positions, setPositions] = useState<EntityItem[]>([
    { id: crypto.randomUUID(), name: '', wikidataId: '' },
  ])

  const [birthplaces, setBirthplaces] = useState<EntityItem[]>([
    { id: crypto.randomUUID(), name: '', wikidataId: '' },
  ])

  const [citizenships, setCitizenships] = useState<EntityItem[]>([
    { id: crypto.randomUUID(), name: '', wikidataId: '' },
  ])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    // Convert form data to flat array of properties
    const properties: Property[] = []

    // Add birth date if provided
    if (birthDate) {
      const [year, month, day] = birthDate.split('-')
      const wikidataDate = `+${year}-${month}-${day}T00:00:00Z`
      properties.push({
        id: crypto.randomUUID(),
        type: PropertyType.P569,
        value: wikidataDate,
        value_precision: birthDatePrecision,
      })
    }

    // Add death date if provided
    if (deathDate) {
      const [year, month, day] = deathDate.split('-')
      const wikidataDate = `+${year}-${month}-${day}T00:00:00Z`
      properties.push({
        id: crypto.randomUUID(),
        type: PropertyType.P570,
        value: wikidataDate,
        value_precision: deathDatePrecision,
      })
    }

    // Add positions with qualifiers
    positions.forEach((position) => {
      if (position.wikidataId && position.name) {
        const qualifiers: Record<string, unknown> = {}

        // Add start date qualifier (P580) if provided
        if (position.startDate) {
          const [year, month, day] = position.startDate.split('-')
          qualifiers.P580 = [
            {
              datavalue: {
                value: {
                  time: `+${year}-${month}-${day}T00:00:00Z`,
                  precision: 11,
                },
              },
            },
          ]
        }

        // Add end date qualifier (P582) if provided
        if (position.endDate) {
          const [year, month, day] = position.endDate.split('-')
          qualifiers.P582 = [
            {
              datavalue: {
                value: {
                  time: `+${year}-${month}-${day}T00:00:00Z`,
                  precision: 11,
                },
              },
            },
          ]
        }

        properties.push({
          id: crypto.randomUUID(),
          type: PropertyType.P39,
          entity_id: position.wikidataId,
          entity_name: position.name,
          qualifiers,
        })
      }
    })

    // Add birthplaces
    birthplaces.forEach((birthplace) => {
      if (birthplace.wikidataId && birthplace.name) {
        properties.push({
          id: crypto.randomUUID(),
          type: PropertyType.P19,
          entity_id: birthplace.wikidataId,
          entity_name: birthplace.name,
        })
      }
    })

    // Add citizenships
    citizenships.forEach((citizenship) => {
      if (citizenship.wikidataId && citizenship.name) {
        properties.push({
          id: crypto.randomUUID(),
          type: PropertyType.P27,
          entity_id: citizenship.wikidataId,
          entity_name: citizenship.name,
        })
      }
    })

    // TODO: Implement API integration
    console.log({
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
              <h1 className="text-xl font-semibold text-gray-900">Create New Politician</h1>
              <p className="mt-1 text-sm text-gray-600">
                Add a new politician with their properties and positions.
              </p>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="px-6 py-6 space-y-8">
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

                {/* Dates */}
                <div className="space-y-6">
                  <h2 className="text-lg font-medium text-gray-900">Dates</h2>

                  <div>
                    <label
                      htmlFor="birthDate"
                      className="block text-sm font-medium text-gray-700 mb-2"
                    >
                      Birth Date
                    </label>
                    <div className="flex gap-3">
                      <Input
                        type="date"
                        id="birthDate"
                        value={birthDate}
                        onChange={(e) => setBirthDate(e.target.value)}
                        className="flex-1"
                      />
                      <select
                        value={birthDatePrecision}
                        onChange={(e) => setBirthDatePrecision(Number(e.target.value))}
                        className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-gray-900"
                      >
                        <option value={11}>Day</option>
                        <option value={10}>Month</option>
                        <option value={9}>Year</option>
                      </select>
                    </div>
                  </div>

                  <div>
                    <label
                      htmlFor="deathDate"
                      className="block text-sm font-medium text-gray-700 mb-2"
                    >
                      Death Date
                    </label>
                    <div className="flex gap-3">
                      <Input
                        type="date"
                        id="deathDate"
                        value={deathDate}
                        onChange={(e) => setDeathDate(e.target.value)}
                        className="flex-1"
                      />
                      <select
                        value={deathDatePrecision}
                        onChange={(e) => setDeathDatePrecision(Number(e.target.value))}
                        className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-gray-900"
                      >
                        <option value={11}>Day</option>
                        <option value={10}>Month</option>
                        <option value={9}>Year</option>
                      </select>
                    </div>
                  </div>
                </div>

                {/* Political Positions */}
                <EntitySelector
                  label="Political Positions"
                  items={positions}
                  onItemsChange={setPositions}
                  showQualifiers={true}
                  qualifierLabels={{ start: 'Start Date', end: 'End Date' }}
                />

                {/* Birthplaces */}
                <EntitySelector
                  label="Birthplaces"
                  items={birthplaces}
                  onItemsChange={setBirthplaces}
                />

                {/* Citizenships */}
                <EntitySelector
                  label="Citizenships"
                  items={citizenships}
                  onItemsChange={setCitizenships}
                />
              </div>

              {/* Footer Actions */}
              <div className="px-6 py-4 border-t border-gray-200 flex justify-between">
                <button
                  type="button"
                  onClick={() => window.history.back()}
                  className="px-4 py-2 text-gray-700 font-medium rounded-md hover:bg-gray-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-6 py-3 bg-indigo-600 text-white font-medium rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Create Politician
                </button>
              </div>
            </form>
          </div>
        </div>
      </main>
    </>
  )
}
