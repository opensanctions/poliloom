import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent, render } from '@testing-library/react'
import '@/test/highlight-mocks'
import { EvaluationView } from './EvaluationView'
import {
  mockPoliticianWithDifferentSources,
  mockPoliticianWithEdgeCases,
  mockArchivedPage,
  mockArchivedPage2,
  mockArchivedPage3,
  mockSourceResponse,
} from '@/test/mock-data'

vi.mock('@/contexts/UserPreferencesContext', () => ({
  useUserPreferences: () => ({
    isAdvancedMode: false,
  }),
}))

describe('EvaluationView', () => {
  beforeEach(() => {
    CSS.highlights.clear()
  })

  describe('single politician - archived page handling', () => {
    it('auto-loads the first property with an archived page on mount', () => {
      render(
        <EvaluationView
          politicians={[mockPoliticianWithDifferentSources]}
          archivedPagesApiPath="/api/archived-pages"
          footer={() => <div>Footer</div>}
        />,
      )

      const iframe = screen.getByTitle('Archived Page') as HTMLIFrameElement
      expect(iframe).toBeInTheDocument()
      expect(iframe.src).toContain(`/api/archived-pages/${mockArchivedPage.id}/html`)

      const viewButtons = screen.getAllByRole('button', { name: /• View|• Viewing/ })
      expect(viewButtons[0]).toHaveTextContent('• Viewing')
    })

    it('clicking View on a property updates the iframe to show that archived page', () => {
      render(
        <EvaluationView
          politicians={[mockPoliticianWithDifferentSources]}
          archivedPagesApiPath="/api/archived-pages"
          footer={() => <div>Footer</div>}
        />,
      )

      const iframe = screen.getByTitle('Archived Page') as HTMLIFrameElement
      expect(iframe.src).toContain(`/api/archived-pages/${mockArchivedPage.id}/html`)

      const viewButtons = screen.getAllByRole('button', { name: /• View|• Viewing/ })
      const secondViewButton = viewButtons.find((btn) => btn.textContent === '• View')
      expect(secondViewButton).toBeDefined()
      fireEvent.click(secondViewButton!)

      expect(iframe.src).toContain(`/api/archived-pages/${mockArchivedPage2.id}/html`)
      expect(secondViewButton).toHaveTextContent('• Viewing')
    })

    it('switching between properties with different archived pages updates the iframe', () => {
      render(
        <EvaluationView
          politicians={[mockPoliticianWithDifferentSources]}
          archivedPagesApiPath="/api/archived-pages"
          footer={() => <div>Footer</div>}
        />,
      )

      const iframe = screen.getByTitle('Archived Page') as HTMLIFrameElement
      expect(iframe.src).toContain(`/api/archived-pages/${mockArchivedPage.id}/html`)

      const viewButtons = screen.getAllByRole('button', { name: /• View|• Viewing/ })
      expect(viewButtons.length).toBe(3)

      fireEvent.click(viewButtons[1])
      expect(iframe.src).toContain(`/api/archived-pages/${mockArchivedPage2.id}/html`)

      fireEvent.click(viewButtons[2])
      expect(iframe.src).toContain(`/api/archived-pages/${mockArchivedPage3.id}/html`)

      fireEvent.click(viewButtons[0])
      expect(iframe.src).toContain(`/api/archived-pages/${mockArchivedPage.id}/html`)
    })

    it('only the active property View button shows "Viewing"', () => {
      render(
        <EvaluationView
          politicians={[mockPoliticianWithDifferentSources]}
          archivedPagesApiPath="/api/archived-pages"
          footer={() => <div>Footer</div>}
        />,
      )

      const viewButtons = screen.getAllByRole('button', { name: /• View|• Viewing/ })

      expect(viewButtons[0]).toHaveTextContent('• Viewing')
      expect(viewButtons[1]).toHaveTextContent('• View')
      expect(viewButtons[2]).toHaveTextContent('• View')

      fireEvent.click(viewButtons[1])

      expect(viewButtons[0]).toHaveTextContent('• View')
      expect(viewButtons[1]).toHaveTextContent('• Viewing')
      expect(viewButtons[2]).toHaveTextContent('• View')

      fireEvent.click(viewButtons[2])

      expect(viewButtons[0]).toHaveTextContent('• View')
      expect(viewButtons[1]).toHaveTextContent('• View')
      expect(viewButtons[2]).toHaveTextContent('• Viewing')
    })

    it('does not show View button for Wikidata statements even if they have archived pages', () => {
      render(
        <EvaluationView
          politicians={[mockPoliticianWithEdgeCases]}
          archivedPagesApiPath="/api/archived-pages"
          footer={() => <div>Footer</div>}
        />,
      )

      const viewButtons = screen.getAllByRole('button', { name: /• View|• Viewing/ })
      expect(viewButtons.length).toBe(1)
    })
  })

  describe('multiple politicians', () => {
    it('renders multiple politicians with headers', () => {
      render(
        <EvaluationView
          politicians={mockSourceResponse.politicians}
          footer={() => <div>Footer</div>}
        />,
      )

      expect(screen.getByText('Source Politician A')).toBeInTheDocument()
      expect(screen.getByText('Source Politician B')).toBeInTheDocument()
    })

    it('renders properties for each politician', () => {
      render(
        <EvaluationView
          politicians={mockSourceResponse.politicians}
          footer={() => <div>Footer</div>}
        />,
      )

      // Politician A has birth date and position
      expect(screen.getByText('Birth Date')).toBeInTheDocument()
      expect(screen.getByText('Mayor of Test City')).toBeInTheDocument()

      // Politician B has citizenship
      expect(screen.getByText('France')).toBeInTheDocument()
    })

    it('auto-loads the first archived page on mount', () => {
      render(
        <EvaluationView
          politicians={mockSourceResponse.politicians}
          archivedPagesApiPath="/api/archived-pages"
          footer={() => <div>Footer</div>}
        />,
      )

      const iframe = screen.getByTitle('Archived Page') as HTMLIFrameElement
      expect(iframe).toBeInTheDocument()
      expect(iframe.src).toContain(
        `/api/archived-pages/${mockSourceResponse.archived_page.id}/html`,
      )
    })

    it('accept/reject toggles work per politician', () => {
      render(
        <EvaluationView
          politicians={mockSourceResponse.politicians}
          footer={() => <div>Footer</div>}
        />,
      )

      // Find accept buttons - should have one per non-wikidata property (3 total)
      const acceptButtons = screen.getAllByRole('button', { name: /accept/i })
      expect(acceptButtons.length).toBe(3)

      // Click accept on first property
      fireEvent.click(acceptButtons[0])

      // The button should now show as active (re-query to check state)
      const rejectButtons = screen.getAllByRole('button', { name: /reject/i })
      expect(rejectButtons.length).toBe(3)
    })

    it('renders footer', () => {
      render(
        <EvaluationView
          politicians={mockSourceResponse.politicians}
          footer={() => <div data-testid="test-footer">Custom Footer</div>}
        />,
      )

      expect(screen.getByTestId('test-footer')).toBeInTheDocument()
      expect(screen.getByText('Custom Footer')).toBeInTheDocument()
    })
  })
})
