'use client'

import { useState } from 'react'
import { Property, PropertyType } from '@/types'
import { Input } from '@/components/ui/Input'
import { Button } from '@/components/ui/Button'
import { Select } from '@/components/ui/Select'
import { EntitySelector } from './EntitySelector'

const precisionOptions = [
  { value: '11', label: 'Day' },
  { value: '10', label: 'Month' },
  { value: '9', label: 'Year' },
]

const propertyTypeOptions = [
  { value: '', label: 'Select a property type...' },
  { value: PropertyType.P569, label: 'Birth Date (P569)' },
  { value: PropertyType.P570, label: 'Death Date (P570)' },
  { value: PropertyType.P39, label: 'Position Held (P39)' },
  { value: PropertyType.P19, label: 'Place of Birth (P19)' },
  { value: PropertyType.P27, label: 'Country of Citizenship (P27)' },
]

interface AddPropertyFormProps {
  onAddProperty: (property: Property) => void
}

export function AddPropertyForm({ onAddProperty }: AddPropertyFormProps) {
  const [sourceUrl, setSourceUrl] = useState('')
  const [propertyType, setPropertyType] = useState<PropertyType | ''>('')

  // Date properties (P569, P570)
  const [dateValue, setDateValue] = useState('')
  const [datePrecision, setDatePrecision] = useState(11)

  // Entity-based properties (P39, P19, P27)
  const [selectedEntity, setSelectedEntity] = useState<{
    wikidata_id: string
    name: string
  } | null>(null)

  // Position qualifiers (P39 only)
  const [startDate, setStartDate] = useState('')
  const [startDatePrecision, setStartDatePrecision] = useState(11)
  const [endDate, setEndDate] = useState('')
  const [endDatePrecision, setEndDatePrecision] = useState(11)

  // Date conversion helpers
  const htmlDateToWikidata = (htmlDate: string): string => {
    const [year, month, day] = htmlDate.split('-')
    return `+${year}-${month}-${day}T00:00:00Z`
  }

  const buildTimeQualifier = (htmlDate: string, precision: number) => {
    return {
      datatype: 'time',
      snaktype: 'value',
      datavalue: {
        type: 'time',
        value: {
          time: htmlDateToWikidata(htmlDate),
          after: 0,
          before: 0,
          timezone: 0,
          precision: precision,
          calendarmodel: 'http://www.wikidata.org/entity/Q1985727',
        },
      },
    }
  }

  const resetForm = () => {
    setPropertyType('')
    setDateValue('')
    setDatePrecision(11)
    setSelectedEntity(null)
    setStartDate('')
    setStartDatePrecision(11)
    setEndDate('')
    setEndDatePrecision(11)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    if (!propertyType || !sourceUrl) return

    let property: Property

    // Build references array with source URL (REST API format)
    const references = [
      {
        property: { id: 'P854' },
        value: { type: 'value', content: sourceUrl },
      },
    ]

    // Date properties (birth/death date)
    if (propertyType === PropertyType.P569 || propertyType === PropertyType.P570) {
      if (!dateValue) return

      property = {
        key: crypto.randomUUID(),
        type: propertyType,
        value: htmlDateToWikidata(dateValue),
        value_precision: datePrecision,
        references,
      }
    }
    // Entity-based properties (positions, birthplaces, citizenships)
    else if (
      propertyType === PropertyType.P39 ||
      propertyType === PropertyType.P19 ||
      propertyType === PropertyType.P27
    ) {
      if (!selectedEntity) return

      property = {
        key: crypto.randomUUID(),
        type: propertyType,
        entity_id: selectedEntity.wikidata_id,
        entity_name: selectedEntity.name,
        references,
      }

      // Add qualifiers for positions
      if (propertyType === PropertyType.P39) {
        const qualifiers: Property['qualifiers'] = {}

        if (startDate) {
          qualifiers.P580 = [buildTimeQualifier(startDate, startDatePrecision)]
        }

        if (endDate) {
          qualifiers.P582 = [buildTimeQualifier(endDate, endDatePrecision)]
        }

        if (Object.keys(qualifiers).length > 0) {
          property.qualifiers = qualifiers
        }
      }
    } else {
      return
    }

    onAddProperty(property)
    resetForm()
  }

  const getEntitySearchEndpoint = () => {
    switch (propertyType) {
      case PropertyType.P39:
        return '/api/positions/search'
      case PropertyType.P19:
        return '/api/locations/search'
      case PropertyType.P27:
        return '/api/countries/search'
      default:
        return ''
    }
  }

  const getEntitySearchPlaceholder = () => {
    switch (propertyType) {
      case PropertyType.P39:
        return 'Search for positions...'
      case PropertyType.P19:
        return 'Search for birthplaces...'
      case PropertyType.P27:
        return 'Search for countries...'
      default:
        return ''
    }
  }

  const isFormValid = () => {
    if (!propertyType || !sourceUrl) return false

    if (propertyType === PropertyType.P569 || propertyType === PropertyType.P570) {
      return dateValue !== ''
    }

    if (
      propertyType === PropertyType.P39 ||
      propertyType === PropertyType.P19 ||
      propertyType === PropertyType.P27
    ) {
      return selectedEntity !== null
    }

    return false
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-4 p-4 border border-border-strong rounded-md bg-surface-muted"
    >
      <h3 className="text-md font-medium text-foreground">Add Property</h3>

      {/* Source URL */}
      <div>
        <label
          htmlFor="sourceUrl"
          className="block text-sm font-medium text-foreground-secondary mb-1"
        >
          Source URL <span className="text-danger-subtle">*</span>
        </label>
        <Input
          id="sourceUrl"
          type="url"
          value={sourceUrl}
          onChange={(e) => setSourceUrl(e.target.value)}
          placeholder="https://example.com/politician-page"
          required
        />
        <p className="mt-1 text-xs text-foreground-muted">
          This URL will be used as a reference for all properties you add
        </p>
      </div>

      {/* Property Type Selector */}
      <Select
        label="Property Type"
        options={propertyTypeOptions}
        value={propertyType}
        onChange={(value) => {
          setPropertyType(value as PropertyType)
          // Reset form fields when type changes
          setDateValue('')
          setSelectedEntity(null)
          setStartDate('')
          setEndDate('')
        }}
        required
      />

      {/* Date input for birth/death dates */}
      {(propertyType === PropertyType.P569 || propertyType === PropertyType.P570) && (
        <div>
          <label
            htmlFor="dateValue"
            className="block text-sm font-medium text-foreground-secondary mb-1"
          >
            Date
          </label>
          <div className="flex gap-2">
            <Input
              id="dateValue"
              type="date"
              value={dateValue}
              onChange={(e) => setDateValue(e.target.value)}
              className="flex-1"
              required
            />
            <Select
              options={precisionOptions}
              value={String(datePrecision)}
              onChange={(value) => setDatePrecision(Number(value))}
            />
          </div>
        </div>
      )}

      {/* Entity selector for entity-based properties */}
      {(propertyType === PropertyType.P39 ||
        propertyType === PropertyType.P19 ||
        propertyType === PropertyType.P27) && (
        <EntitySelector
          searchEndpoint={getEntitySearchEndpoint()}
          placeholder={getEntitySearchPlaceholder()}
          label={
            propertyType === PropertyType.P39
              ? 'Position'
              : propertyType === PropertyType.P19
                ? 'Birthplace'
                : 'Country'
          }
          selectedEntity={
            selectedEntity
              ? {
                  name: selectedEntity.name,
                  id: selectedEntity.wikidata_id,
                }
              : null
          }
          onSelect={(result) => {
            setSelectedEntity({
              wikidata_id: result.wikidata_id!,
              name: result.name,
            })
          }}
          onClear={() => setSelectedEntity(null)}
        />
      )}

      {/* Date qualifiers for positions */}
      {propertyType === PropertyType.P39 && selectedEntity && (
        <div className="space-y-3 pt-3 border-t border-border-strong">
          <h4 className="text-sm font-medium text-foreground-secondary">
            Position Dates (Optional)
          </h4>

          {/* Start Date */}
          <div>
            <label
              htmlFor="startDate"
              className="block text-sm font-medium text-foreground-secondary mb-1"
            >
              Start Date
            </label>
            <div className="flex gap-2">
              <Input
                id="startDate"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="flex-1"
              />
              <Select
                options={precisionOptions}
                value={String(startDatePrecision)}
                onChange={(value) => setStartDatePrecision(Number(value))}
                disabled={!startDate}
              />
            </div>
          </div>

          {/* End Date */}
          <div>
            <label
              htmlFor="endDate"
              className="block text-sm font-medium text-foreground-secondary mb-1"
            >
              End Date
            </label>
            <div className="flex gap-2">
              <Input
                id="endDate"
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="flex-1"
              />
              <Select
                options={precisionOptions}
                value={String(endDatePrecision)}
                onChange={(value) => setEndDatePrecision(Number(value))}
                disabled={!endDate}
              />
            </div>
          </div>
        </div>
      )}

      {/* Submit Button */}
      <div className="flex gap-2 pt-2">
        <Button type="submit" disabled={!isFormValid()} className="flex-1">
          Add Property
        </Button>
        {propertyType && (
          <Button type="button" variant="secondary" onClick={resetForm}>
            Clear
          </Button>
        )}
      </div>
    </form>
  )
}
