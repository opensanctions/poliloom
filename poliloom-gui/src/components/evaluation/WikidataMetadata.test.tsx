import { render, screen, fireEvent } from '@testing-library/react'
import { WikidataMetadataButtons, WikidataMetadataPanel } from './WikidataMetadata'
import { describe, it, expect, vi } from 'vitest'
import type { RestSnak, RestStatement } from '@/types'

const timeSnak = (propertyId: string, time: string): RestSnak => ({
  property: { id: propertyId },
  value: {
    type: 'value',
    content: { time, precision: 11, calendarmodel: 'http://www.wikidata.org/entity/Q1985727' },
  },
})

const urlReference: RestStatement['references'][number] = {
  hash: 'ref-1',
  parts: [{ property: { id: 'P854' }, value: { type: 'value', content: 'https://example.com' } }],
}

describe('WikidataMetadataButtons', () => {
  const mockOnToggle = vi.fn()

  it('returns null when there are no qualifiers or references', () => {
    const { container } = render(
      <WikidataMetadataButtons
        qualifiers={[]}
        references={[]}
        openSection={null}
        onToggle={mockOnToggle}
      />,
    )

    expect(container.firstChild).toBeNull()
  })

  it('renders qualifiers button when qualifiers exist', () => {
    render(
      <WikidataMetadataButtons
        qualifiers={[timeSnak('P580', '+2020-01-01T00:00:00Z')]}
        references={[]}
        openSection={null}
        onToggle={mockOnToggle}
      />,
    )

    expect(screen.getByText('Qualifiers')).toBeInTheDocument()
  })

  it('renders references button when references exist', () => {
    render(
      <WikidataMetadataButtons
        qualifiers={[]}
        references={[urlReference]}
        openSection={null}
        onToggle={mockOnToggle}
      />,
    )

    expect(screen.getByText('References')).toBeInTheDocument()
  })

  it('renders both buttons when both exist', () => {
    render(
      <WikidataMetadataButtons
        qualifiers={[timeSnak('P580', '+2020-01-01T00:00:00Z')]}
        references={[urlReference]}
        openSection={null}
        onToggle={mockOnToggle}
      />,
    )

    expect(screen.getByText('Qualifiers')).toBeInTheDocument()
    expect(screen.getByText('References')).toBeInTheDocument()
  })

  it('calls onToggle when qualifiers button is clicked', () => {
    render(
      <WikidataMetadataButtons
        qualifiers={[timeSnak('P580', '+2020-01-01T00:00:00Z')]}
        references={[]}
        openSection={null}
        onToggle={mockOnToggle}
      />,
    )

    fireEvent.click(screen.getByText('Qualifiers'))

    expect(mockOnToggle).toHaveBeenCalledWith('qualifiers')
  })

  it('calls onToggle when references button is clicked', () => {
    render(
      <WikidataMetadataButtons
        qualifiers={[]}
        references={[urlReference]}
        openSection={null}
        onToggle={mockOnToggle}
      />,
    )

    fireEvent.click(screen.getByText('References'))

    expect(mockOnToggle).toHaveBeenCalledWith('references')
  })

  it('shows correct arrow rotation when panel is closed', () => {
    const { container } = render(
      <WikidataMetadataButtons
        qualifiers={[timeSnak('P580', '+2020-01-01T00:00:00Z')]}
        references={[]}
        openSection={null}
        onToggle={mockOnToggle}
      />,
    )

    const arrow = container.querySelector('.transition-transform')
    expect(arrow).toHaveClass('-rotate-90')
  })

  it('shows correct arrow rotation when panel is open', () => {
    const { container } = render(
      <WikidataMetadataButtons
        qualifiers={[timeSnak('P580', '+2020-01-01T00:00:00Z')]}
        references={[]}
        openSection="qualifiers"
        onToggle={mockOnToggle}
      />,
    )

    const arrow = container.querySelector('.transition-transform')
    expect(arrow).not.toHaveClass('-rotate-90')
  })
})

describe('WikidataMetadataPanel', () => {
  it('renders nothing when openSection is null', () => {
    const { container } = render(
      <WikidataMetadataPanel
        qualifiers={[timeSnak('P580', '+2020-01-01T00:00:00Z')]}
        references={[]}
        openSection={null}
      />,
    )

    expect(container.firstChild).toBeNull()
  })

  it('renders qualifiers JSON when openSection is qualifiers', () => {
    render(
      <WikidataMetadataPanel
        qualifiers={[timeSnak('P580', '+2020-01-01T00:00:00Z')]}
        references={[]}
        openSection="qualifiers"
      />,
    )

    expect(screen.getByText(/"P580"/)).toBeInTheDocument()
  })

  it('renders references JSON when openSection is references', () => {
    render(
      <WikidataMetadataPanel
        qualifiers={[]}
        references={[urlReference]}
        openSection="references"
      />,
    )

    expect(screen.getByText(/"P854"/)).toBeInTheDocument()
  })

  it('renders the panel on a muted surface', () => {
    const { container } = render(
      <WikidataMetadataPanel
        qualifiers={[timeSnak('P580', '+2020-01-01T00:00:00Z')]}
        references={[]}
        openSection="qualifiers"
      />,
    )

    const panel = container.querySelector('.bg-surface-muted')
    expect(panel).toBeInTheDocument()
  })
})
