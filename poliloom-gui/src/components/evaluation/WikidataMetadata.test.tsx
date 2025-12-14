import { render, screen, fireEvent } from '@testing-library/react'
import { WikidataMetadataButtons, WikidataMetadataPanel } from './WikidataMetadata'
import { describe, it, expect, vi } from 'vitest'

describe('WikidataMetadataButtons', () => {
  const mockOnToggle = vi.fn()

  it('returns null when there are no qualifiers or references', () => {
    const { container } = render(
      <WikidataMetadataButtons openSection={null} onToggle={mockOnToggle} />,
    )

    expect(container.firstChild).toBeNull()
  })

  it('renders qualifiers button when qualifiers exist', () => {
    const qualifiers = { P580: [{ datavalue: { value: 'test' } }] }

    render(
      <WikidataMetadataButtons
        qualifiers={qualifiers}
        openSection={null}
        onToggle={mockOnToggle}
      />,
    )

    expect(screen.getByText('Qualifiers')).toBeInTheDocument()
  })

  it('renders references button when references exist', () => {
    const references = [{ url: 'https://example.com', title: 'Test' }]

    render(
      <WikidataMetadataButtons
        references={references}
        openSection={null}
        onToggle={mockOnToggle}
      />,
    )

    expect(screen.getByText('References')).toBeInTheDocument()
  })

  it('renders both buttons when both exist', () => {
    const qualifiers = { P580: [{ datavalue: { value: 'test' } }] }
    const references = [{ url: 'https://example.com', title: 'Test' }]

    render(
      <WikidataMetadataButtons
        qualifiers={qualifiers}
        references={references}
        openSection={null}
        onToggle={mockOnToggle}
      />,
    )

    expect(screen.getByText('Qualifiers')).toBeInTheDocument()
    expect(screen.getByText('References')).toBeInTheDocument()
  })

  it('shows warning emoji when panel is closed', () => {
    const qualifiers = { P580: [{ datavalue: { value: 'test' } }] }

    render(
      <WikidataMetadataButtons
        qualifiers={qualifiers}
        openSection={null}
        onToggle={mockOnToggle}
      />,
    )

    expect(screen.getByText('⚠️')).toBeInTheDocument()
  })

  it('does not show warning emoji when panel is open', () => {
    const qualifiers = { P580: [{ datavalue: { value: 'test' } }] }

    render(
      <WikidataMetadataButtons
        qualifiers={qualifiers}
        openSection="qualifiers"
        onToggle={mockOnToggle}
      />,
    )

    expect(screen.queryByText('⚠️')).not.toBeInTheDocument()
  })

  it('calls onToggle when qualifiers button is clicked', () => {
    const qualifiers = { P580: [{ datavalue: { value: 'test' } }] }

    render(
      <WikidataMetadataButtons
        qualifiers={qualifiers}
        openSection={null}
        onToggle={mockOnToggle}
      />,
    )

    fireEvent.click(screen.getByText('Qualifiers'))

    expect(mockOnToggle).toHaveBeenCalledWith('qualifiers')
  })

  it('calls onToggle when references button is clicked', () => {
    const references = [{ url: 'https://example.com', title: 'Test' }]

    render(
      <WikidataMetadataButtons
        references={references}
        openSection={null}
        onToggle={mockOnToggle}
      />,
    )

    fireEvent.click(screen.getByText('References'))

    expect(mockOnToggle).toHaveBeenCalledWith('references')
  })

  it('shows correct arrow rotation when panel is closed', () => {
    const qualifiers = { P580: [{ datavalue: { value: 'test' } }] }

    const { container } = render(
      <WikidataMetadataButtons
        qualifiers={qualifiers}
        openSection={null}
        onToggle={mockOnToggle}
      />,
    )

    const arrow = container.querySelector('.transition-transform')
    expect(arrow).toHaveClass('-rotate-90')
  })

  it('shows correct arrow rotation when panel is open', () => {
    const qualifiers = { P580: [{ datavalue: { value: 'test' } }] }

    const { container } = render(
      <WikidataMetadataButtons
        qualifiers={qualifiers}
        openSection="qualifiers"
        onToggle={mockOnToggle}
      />,
    )

    const arrow = container.querySelector('.transition-transform')
    expect(arrow).not.toHaveClass('-rotate-90')
  })

  it('renders buttons with red color', () => {
    const qualifiers = { P580: [{ datavalue: { value: 'test' } }] }

    render(
      <WikidataMetadataButtons
        qualifiers={qualifiers}
        openSection={null}
        onToggle={mockOnToggle}
      />,
    )

    const button = screen.getByText('Qualifiers').closest('button')
    expect(button).toHaveClass('text-danger-foreground')
  })
})

describe('WikidataMetadataPanel', () => {
  it('renders nothing when openSection is null', () => {
    const qualifiers = { P580: [{ datavalue: { value: 'test' } }] }

    const { container } = render(
      <WikidataMetadataPanel qualifiers={qualifiers} openSection={null} />,
    )

    expect(container.firstChild).toBeNull()
  })

  it('renders qualifiers JSON when openSection is qualifiers', () => {
    const qualifiers = { P580: [{ datavalue: { value: 'test' } }] }

    render(<WikidataMetadataPanel qualifiers={qualifiers} openSection="qualifiers" />)

    expect(screen.getByText(/"P580"/)).toBeInTheDocument()
  })

  it('renders references JSON when openSection is references', () => {
    const references = [{ url: 'https://example.com', title: 'Test' }]

    render(<WikidataMetadataPanel references={references} openSection="references" />)

    expect(screen.getByText(/"url"/)).toBeInTheDocument()
  })

  it('shows red background', () => {
    const qualifiers = { P580: [{ datavalue: { value: 'test' } }] }

    const { container } = render(
      <WikidataMetadataPanel qualifiers={qualifiers} openSection="qualifiers" />,
    )

    const panel = container.querySelector('.bg-danger-deep')
    expect(panel).toBeInTheDocument()
  })

  it('shows warning text inside panel', () => {
    const qualifiers = { P580: [{ datavalue: { value: 'test' } }] }

    render(<WikidataMetadataPanel qualifiers={qualifiers} openSection="qualifiers" />)

    expect(screen.getByText('Metadata will be lost ⚠️')).toBeInTheDocument()
  })
})
