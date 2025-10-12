import { render, screen, fireEvent } from '@testing-library/react'
import { act } from 'react'
import { WikidataMetadata } from './WikidataMetadata'
import { describe, it, expect, beforeEach } from 'vitest'

describe('WikidataMetadata', () => {
  beforeEach(() => {
    // Reset any state between tests
  })

  describe('Basic Rendering', () => {
    it('shows "No metadata" when there are no qualifiers or references', () => {
      render(<WikidataMetadata />)

      expect(screen.getByText('No metadata')).toBeInTheDocument()
    })

    it('renders qualifiers button when qualifiers exist', () => {
      const qualifiers = { P580: [{ datavalue: { value: 'test' } }] }

      render(<WikidataMetadata qualifiers={qualifiers} />)

      expect(screen.getByText('Qualifiers')).toBeInTheDocument()
    })

    it('renders references button when references exist', () => {
      const references = [{ url: 'https://example.com', title: 'Test' }]

      render(<WikidataMetadata references={references} />)

      expect(screen.getByText('References')).toBeInTheDocument()
    })

    it('renders both buttons when both exist', () => {
      const qualifiers = { P580: [{ datavalue: { value: 'test' } }] }
      const references = [{ url: 'https://example.com', title: 'Test' }]

      render(<WikidataMetadata qualifiers={qualifiers} references={references} />)

      expect(screen.getByText('Qualifiers')).toBeInTheDocument()
      expect(screen.getByText('References')).toBeInTheDocument()
    })
  })

  describe('Auto-Open Behavior When Discarding', () => {
    it('auto-opens qualifiers panel when isDiscarding is true and qualifiers exist', () => {
      const qualifiers = { P580: [{ datavalue: { value: 'test' } }] }

      act(() => {
        render(<WikidataMetadata qualifiers={qualifiers} isDiscarding={true} />)
      })

      // Panel should be open - check for the JSON content
      expect(screen.getByText(/"P580"/)).toBeInTheDocument()
    })

    it('auto-opens references panel when isDiscarding is true and only references exist', () => {
      const references = [{ url: 'https://example.com', title: 'Test' }]

      act(() => {
        render(<WikidataMetadata references={references} isDiscarding={true} />)
      })

      // Panel should be open - check for the JSON content
      expect(screen.getByText(/"url"/)).toBeInTheDocument()
    })

    it('prefers qualifiers over references when both exist', () => {
      const qualifiers = { P580: [{ datavalue: { value: 'test' } }] }
      const references = [{ url: 'https://example.com', title: 'Test' }]

      act(() => {
        render(
          <WikidataMetadata qualifiers={qualifiers} references={references} isDiscarding={true} />,
        )
      })

      // Qualifiers should be open
      expect(screen.getByText(/"P580"/)).toBeInTheDocument()
      // References should not be visible
      expect(screen.queryByText(/"url"/)).not.toBeInTheDocument()
    })

    it('shows red background (bg-red-900) in the panel when discarding', () => {
      const qualifiers = { P580: [{ datavalue: { value: 'test' } }] }

      let container: HTMLElement
      act(() => {
        const result = render(<WikidataMetadata qualifiers={qualifiers} isDiscarding={true} />)
        container = result.container
      })

      const panel = container!.querySelector('.bg-red-900')
      expect(panel).toBeInTheDocument()
    })

    it('shows "Metadata will be lost ⚠" text inside the panel when discarding', () => {
      const qualifiers = { P580: [{ datavalue: { value: 'test' } }] }

      act(() => {
        render(<WikidataMetadata qualifiers={qualifiers} isDiscarding={true} />)
      })

      expect(screen.getByText('Metadata will be lost ⚠')).toBeInTheDocument()
    })

    it('shows warning message when panel is closed while discarding', () => {
      const qualifiers = { P580: [{ datavalue: { value: 'test' } }] }

      act(() => {
        render(<WikidataMetadata qualifiers={qualifiers} isDiscarding={true} />)
      })

      // Close the auto-opened panel
      act(() => {
        fireEvent.click(screen.getByText('Qualifiers'))
      })

      // Warning should appear
      expect(screen.getByText('⚠ Metadata will be lost')).toBeInTheDocument()
    })
  })

  describe('Manual Panel Control While Discarding', () => {
    it('allows user to manually close the auto-opened panel', () => {
      const qualifiers = { P580: [{ datavalue: { value: 'test' } }] }

      act(() => {
        render(<WikidataMetadata qualifiers={qualifiers} isDiscarding={true} />)
      })

      // Panel should be open initially
      expect(screen.getByText(/"P580"/)).toBeInTheDocument()

      // Close the panel
      act(() => {
        fireEvent.click(screen.getByText('Qualifiers'))
      })

      // Panel should be closed
      expect(screen.queryByText(/"P580"/)).not.toBeInTheDocument()
    })

    it('allows user to switch from qualifiers to references panel', () => {
      const qualifiers = { P580: [{ datavalue: { value: 'test' } }] }
      const references = [{ url: 'https://example.com', title: 'Test' }]

      act(() => {
        render(
          <WikidataMetadata qualifiers={qualifiers} references={references} isDiscarding={true} />,
        )
      })

      // Qualifiers should be open initially
      expect(screen.getByText(/"P580"/)).toBeInTheDocument()

      // Switch to references
      act(() => {
        fireEvent.click(screen.getByText('References'))
      })

      // References should be open, qualifiers should be closed
      expect(screen.getByText(/"url"/)).toBeInTheDocument()
      expect(screen.queryByText(/"P580"/)).not.toBeInTheDocument()
    })

    it('allows user to manually re-open a closed panel', () => {
      const qualifiers = { P580: [{ datavalue: { value: 'test' } }] }

      act(() => {
        render(<WikidataMetadata qualifiers={qualifiers} isDiscarding={true} />)
      })

      // Close the panel
      act(() => {
        fireEvent.click(screen.getByText('Qualifiers'))
      })
      expect(screen.queryByText(/"P580"/)).not.toBeInTheDocument()

      // Re-open the panel
      act(() => {
        fireEvent.click(screen.getByText('Qualifiers'))
      })
      expect(screen.getByText(/"P580"/)).toBeInTheDocument()
    })

    it('shows warning message when both panels are closed while discarding', () => {
      const qualifiers = { P580: [{ datavalue: { value: 'test' } }] }
      const references = [{ url: 'https://example.com', title: 'Test' }]

      act(() => {
        render(
          <WikidataMetadata qualifiers={qualifiers} references={references} isDiscarding={true} />,
        )
      })

      // Close the auto-opened qualifiers panel
      act(() => {
        fireEvent.click(screen.getByText('Qualifiers'))
      })

      // Warning should be visible since both panels are closed
      expect(screen.getByText('⚠ Metadata will be lost')).toBeInTheDocument()
    })
  })

  describe('Auto-Close Behavior When Not Discarding', () => {
    it('closes the panel when isDiscarding changes from true to false (auto-opened)', () => {
      const qualifiers = { P580: [{ datavalue: { value: 'test' } }] }

      const { rerender } = render(<WikidataMetadata qualifiers={qualifiers} isDiscarding={true} />)

      // Panel should be open
      expect(screen.getByText(/"P580"/)).toBeInTheDocument()

      // Change isDiscarding to false
      act(() => {
        rerender(<WikidataMetadata qualifiers={qualifiers} isDiscarding={false} />)
      })

      // Panel should be closed
      expect(screen.queryByText(/"P580"/)).not.toBeInTheDocument()
    })

    it('does not close the panel if user manually opened it', () => {
      const qualifiers = { P580: [{ datavalue: { value: 'test' } }] }

      const { rerender } = render(<WikidataMetadata qualifiers={qualifiers} isDiscarding={false} />)

      // Manually open the panel
      act(() => {
        fireEvent.click(screen.getByText('Qualifiers'))
      })
      expect(screen.getByText(/"P580"/)).toBeInTheDocument()

      // Change isDiscarding to true and back to false
      act(() => {
        rerender(<WikidataMetadata qualifiers={qualifiers} isDiscarding={true} />)
      })
      act(() => {
        rerender(<WikidataMetadata qualifiers={qualifiers} isDiscarding={false} />)
      })

      // Panel should still be open because it was manually opened
      expect(screen.getByText(/"P580"/)).toBeInTheDocument()
    })

    it('shows gray background (bg-gray-700) when not discarding', () => {
      const qualifiers = { P580: [{ datavalue: { value: 'test' } }] }

      const { container } = render(<WikidataMetadata qualifiers={qualifiers} />)

      // Open the panel manually
      act(() => {
        fireEvent.click(screen.getByText('Qualifiers'))
      })

      const panel = container.querySelector('.bg-gray-700')
      expect(panel).toBeInTheDocument()
    })

    it('does not show "Metadata will be lost" warning when not discarding', () => {
      const qualifiers = { P580: [{ datavalue: { value: 'test' } }] }

      render(<WikidataMetadata qualifiers={qualifiers} />)

      // Open the panel manually
      act(() => {
        fireEvent.click(screen.getByText('Qualifiers'))
      })

      // No warning message in the panel
      expect(screen.queryByText('Metadata will be lost ⚠')).not.toBeInTheDocument()
    })

    it('does not show warning message when panel is closed and not discarding', () => {
      const qualifiers = { P580: [{ datavalue: { value: 'test' } }] }

      render(<WikidataMetadata qualifiers={qualifiers} isDiscarding={false} />)

      // No warning message
      expect(screen.queryByText('⚠ Metadata will be lost')).not.toBeInTheDocument()
    })
  })

  describe('Toggle Functionality', () => {
    it('opens a closed panel when clicked', () => {
      const qualifiers = { P580: [{ datavalue: { value: 'test' } }] }

      render(<WikidataMetadata qualifiers={qualifiers} />)

      // Panel should be closed initially
      expect(screen.queryByText(/"P580"/)).not.toBeInTheDocument()

      // Click to open
      act(() => {
        fireEvent.click(screen.getByText('Qualifiers'))
      })

      // Panel should be open
      expect(screen.getByText(/"P580"/)).toBeInTheDocument()
    })

    it('closes an open panel when clicked', () => {
      const qualifiers = { P580: [{ datavalue: { value: 'test' } }] }

      render(<WikidataMetadata qualifiers={qualifiers} />)

      // Open the panel
      act(() => {
        fireEvent.click(screen.getByText('Qualifiers'))
      })
      expect(screen.getByText(/"P580"/)).toBeInTheDocument()

      // Close the panel
      act(() => {
        fireEvent.click(screen.getByText('Qualifiers'))
      })
      expect(screen.queryByText(/"P580"/)).not.toBeInTheDocument()
    })

    it('switches from one panel to another', () => {
      const qualifiers = { P580: [{ datavalue: { value: 'test' } }] }
      const references = [{ url: 'https://example.com', title: 'Test' }]

      render(<WikidataMetadata qualifiers={qualifiers} references={references} />)

      // Open qualifiers
      act(() => {
        fireEvent.click(screen.getByText('Qualifiers'))
      })
      expect(screen.getByText(/"P580"/)).toBeInTheDocument()

      // Switch to references
      act(() => {
        fireEvent.click(screen.getByText('References'))
      })
      expect(screen.getByText(/"url"/)).toBeInTheDocument()
      expect(screen.queryByText(/"P580"/)).not.toBeInTheDocument()
    })

    it('shows correct arrow rotation when panel is open', () => {
      const qualifiers = { P580: [{ datavalue: { value: 'test' } }] }

      const { container } = render(<WikidataMetadata qualifiers={qualifiers} />)

      // Find the arrow span
      const arrow = container.querySelector('.transition-transform')

      // Initially closed - should have -rotate-90 class
      expect(arrow).toHaveClass('-rotate-90')

      // Open the panel
      act(() => {
        fireEvent.click(screen.getByText('Qualifiers'))
      })

      // Should not have -rotate-90 class when open
      expect(arrow).not.toHaveClass('-rotate-90')
    })

    it('shows correct arrow rotation when panel is closed', () => {
      const qualifiers = { P580: [{ datavalue: { value: 'test' } }] }

      const { container } = render(<WikidataMetadata qualifiers={qualifiers} />)

      // Open the panel first
      act(() => {
        fireEvent.click(screen.getByText('Qualifiers'))
      })

      const arrow = container.querySelector('.transition-transform')
      expect(arrow).not.toHaveClass('-rotate-90')

      // Close the panel
      act(() => {
        fireEvent.click(screen.getByText('Qualifiers'))
      })

      // Should have -rotate-90 class when closed
      expect(arrow).toHaveClass('-rotate-90')
    })
  })
})
