import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent, render } from '@testing-library/react'
import '@/test/highlight-mocks'
import { PoliticianEvaluationView } from './PoliticianEvaluationView'
import {
  mockPoliticianWithDifferentSources,
  mockPoliticianWithEdgeCases,
  mockArchivedPage,
  mockArchivedPage2,
  mockArchivedPage3,
} from '@/test/mock-data'

vi.mock('@/contexts/UserPreferencesContext', () => ({
  useUserPreferences: () => ({
    isAdvancedMode: false,
  }),
}))

describe('PoliticianEvaluationView', () => {
  beforeEach(() => {
    CSS.highlights.clear()
  })

  describe('archived page handling', () => {
    it('auto-loads the first property with an archived page on mount', () => {
      render(
        <PoliticianEvaluationView
          politician={mockPoliticianWithDifferentSources}
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
        <PoliticianEvaluationView
          politician={mockPoliticianWithDifferentSources}
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
        <PoliticianEvaluationView
          politician={mockPoliticianWithDifferentSources}
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
        <PoliticianEvaluationView
          politician={mockPoliticianWithDifferentSources}
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
        <PoliticianEvaluationView
          politician={mockPoliticianWithEdgeCases}
          archivedPagesApiPath="/api/archived-pages"
          footer={() => <div>Footer</div>}
        />,
      )

      const viewButtons = screen.getAllByRole('button', { name: /• View|• Viewing/ })
      expect(viewButtons.length).toBe(1)
    })
  })
})
