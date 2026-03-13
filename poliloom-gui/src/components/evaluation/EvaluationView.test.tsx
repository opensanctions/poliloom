import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent, render } from '@testing-library/react'
import '@/test/highlight-mocks'
import { EvaluationView } from './EvaluationView'
import type { Politician, SourceResponse, ArchivedPageResponse } from '@/types'
import { PropertyType } from '@/types'

vi.mock('@/contexts/UserPreferencesContext', () => ({
  useUserPreferences: () => ({
    isAdvancedMode: false,
  }),
}))

const archivedPage1: ArchivedPageResponse = {
  id: 'archived-1',
  url: 'https://en.wikipedia.org/wiki/Test',
  content_hash: 'abc',
  fetch_timestamp: '2024-01-01T00:00:00Z',
  status: 'DONE',
}

const archivedPage2: ArchivedPageResponse = {
  id: 'archived-2',
  url: 'https://gov.example.com/official',
  content_hash: 'def',
  fetch_timestamp: '2024-02-01T00:00:00Z',
  status: 'DONE',
}

const archivedPage3: ArchivedPageResponse = {
  id: 'archived-3',
  url: 'https://news.example.com/bio',
  content_hash: 'ghi',
  fetch_timestamp: '2024-03-01T00:00:00Z',
  status: 'DONE',
}

const politicianWithDifferentSources: Politician = {
  id: 'pol-1',
  name: 'Multi-Source Politician',
  wikidata_id: 'Q100',
  archived_pages: [archivedPage1, archivedPage2, archivedPage3],
  properties: [
    {
      id: 'prop-1',
      type: PropertyType.P569,
      value: '+1975-06-15T00:00:00Z',
      value_precision: 11,
      statement_id: null,
      archived_pages: [
        { id: 'ref-1', archived_page_id: archivedPage1.id, supporting_quotes: ['born June 15'] },
      ],
    },
    {
      id: 'prop-2',
      type: PropertyType.P39,
      entity_id: 'Q200',
      entity_name: 'Governor',
      statement_id: null,
      qualifiers: {
        P580: [{ datavalue: { value: { time: '+2018-01-01T00:00:00Z', precision: 11 } } }],
      },
      archived_pages: [
        {
          id: 'ref-2',
          archived_page_id: archivedPage2.id,
          supporting_quotes: ['elected governor'],
        },
      ],
    },
    {
      id: 'prop-3',
      type: PropertyType.P19,
      entity_id: 'Q300',
      entity_name: 'Capital City',
      statement_id: null,
      archived_pages: [
        {
          id: 'ref-3',
          archived_page_id: archivedPage3.id,
          supporting_quotes: ['born in Capital City'],
        },
      ],
    },
  ],
}

const politicianWithEdgeCases: Politician = {
  id: 'pol-2',
  name: 'Edge Case Politician',
  wikidata_id: 'Q101',
  archived_pages: [archivedPage1],
  properties: [
    {
      id: 'prop-wikidata',
      type: PropertyType.P569,
      value: '+1980-01-01T00:00:00Z',
      value_precision: 11,
      statement_id: 'Q101$some-uuid',
      archived_pages: [
        { id: 'ref-w', archived_page_id: archivedPage1.id, supporting_quotes: ['born 1980'] },
      ],
    },
    {
      id: 'prop-extracted',
      type: PropertyType.P569,
      value: '+1980-01-02T00:00:00Z',
      value_precision: 11,
      statement_id: null,
      archived_pages: [
        { id: 'ref-e', archived_page_id: archivedPage1.id, supporting_quotes: ['born Jan 2'] },
      ],
    },
    {
      id: 'pos-wikidata',
      type: PropertyType.P39,
      entity_id: 'Q400',
      entity_name: 'Mayor',
      statement_id: 'Q400$some-uuid',
      qualifiers: {
        P580: [{ datavalue: { value: { time: '+2020-01-01T00:00:00Z', precision: 11 } } }],
        P582: [{ datavalue: { value: { time: '+2024-01-01T00:00:00Z', precision: 11 } } }],
      },
      archived_pages: [],
    },
    {
      id: 'birth-wikidata',
      type: PropertyType.P19,
      entity_id: 'Q500',
      entity_name: 'Test City',
      statement_id: 'Q500$some-uuid',
      archived_pages: [],
    },
  ],
}

const sourceResponse: SourceResponse = {
  archived_page: archivedPage1,
  politicians: [
    {
      id: 'pol-a',
      name: 'Source Politician A',
      wikidata_id: 'Q111',
      archived_pages: [archivedPage1],
      properties: [
        {
          id: 'sp-1',
          type: PropertyType.P569,
          value: '+1970-01-01T00:00:00Z',
          value_precision: 11,
          statement_id: null,
          archived_pages: [
            { id: 'sr-1', archived_page_id: archivedPage1.id, supporting_quotes: ['born 1970'] },
          ],
        },
        {
          id: 'sp-2',
          type: PropertyType.P39,
          entity_id: 'Q555',
          entity_name: 'Mayor of Test City',
          statement_id: null,
          archived_pages: [
            {
              id: 'sr-2',
              archived_page_id: archivedPage1.id,
              supporting_quotes: ['served as mayor'],
            },
          ],
        },
      ],
    },
    {
      id: 'pol-b',
      name: 'Source Politician B',
      wikidata_id: 'Q222',
      archived_pages: [archivedPage1],
      properties: [
        {
          id: 'sp-3',
          type: PropertyType.P27,
          entity_id: 'Q142',
          entity_name: 'France',
          statement_id: null,
          archived_pages: [
            {
              id: 'sr-3',
              archived_page_id: archivedPage1.id,
              supporting_quotes: ['French citizen'],
            },
          ],
        },
      ],
    },
  ],
}

describe('EvaluationView', () => {
  beforeEach(() => {
    CSS.highlights.clear()
  })

  describe('single politician - archived page handling', () => {
    it('auto-loads the first property with an archived page on mount', () => {
      render(
        <EvaluationView
          politicians={[politicianWithDifferentSources]}
          archivedPagesApiPath="/api/archived-pages"
          footer={() => <div>Footer</div>}
        />,
      )

      const iframe = screen.getByTitle('Archived Page') as HTMLIFrameElement
      expect(iframe).toBeInTheDocument()
      expect(iframe.src).toContain(`/api/archived-pages/${archivedPage1.id}/html`)

      const viewButtons = screen.getAllByRole('button', { name: /• View|• Viewing/ })
      expect(viewButtons[0]).toHaveTextContent('• Viewing')
    })

    it('clicking View on a property updates the iframe to show that archived page', () => {
      render(
        <EvaluationView
          politicians={[politicianWithDifferentSources]}
          archivedPagesApiPath="/api/archived-pages"
          footer={() => <div>Footer</div>}
        />,
      )

      const iframe = screen.getByTitle('Archived Page') as HTMLIFrameElement
      expect(iframe.src).toContain(`/api/archived-pages/${archivedPage1.id}/html`)

      const viewButtons = screen.getAllByRole('button', { name: /• View|• Viewing/ })
      const secondViewButton = viewButtons.find((btn) => btn.textContent === '• View')
      expect(secondViewButton).toBeDefined()
      fireEvent.click(secondViewButton!)

      expect(iframe.src).toContain(`/api/archived-pages/${archivedPage2.id}/html`)
      expect(secondViewButton).toHaveTextContent('• Viewing')
    })

    it('switching between properties with different archived pages updates the iframe', () => {
      render(
        <EvaluationView
          politicians={[politicianWithDifferentSources]}
          archivedPagesApiPath="/api/archived-pages"
          footer={() => <div>Footer</div>}
        />,
      )

      const iframe = screen.getByTitle('Archived Page') as HTMLIFrameElement
      expect(iframe.src).toContain(`/api/archived-pages/${archivedPage1.id}/html`)

      const viewButtons = screen.getAllByRole('button', { name: /• View|• Viewing/ })
      expect(viewButtons.length).toBe(3)

      fireEvent.click(viewButtons[1])
      expect(iframe.src).toContain(`/api/archived-pages/${archivedPage2.id}/html`)

      fireEvent.click(viewButtons[2])
      expect(iframe.src).toContain(`/api/archived-pages/${archivedPage3.id}/html`)

      fireEvent.click(viewButtons[0])
      expect(iframe.src).toContain(`/api/archived-pages/${archivedPage1.id}/html`)
    })

    it('only the active property View button shows "Viewing"', () => {
      render(
        <EvaluationView
          politicians={[politicianWithDifferentSources]}
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
          politicians={[politicianWithEdgeCases]}
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
          politicians={sourceResponse.politicians}
          footer={() => <div>Footer</div>}
        />,
      )

      expect(screen.getByText('Source Politician A')).toBeInTheDocument()
      expect(screen.getByText('Source Politician B')).toBeInTheDocument()
    })

    it('renders properties for each politician', () => {
      render(
        <EvaluationView
          politicians={sourceResponse.politicians}
          footer={() => <div>Footer</div>}
        />,
      )

      expect(screen.getByText('Birth Date')).toBeInTheDocument()
      expect(screen.getByText('Mayor of Test City')).toBeInTheDocument()
      expect(screen.getByText('France')).toBeInTheDocument()
    })

    it('auto-loads the first archived page on mount', () => {
      render(
        <EvaluationView
          politicians={sourceResponse.politicians}
          archivedPagesApiPath="/api/archived-pages"
          footer={() => <div>Footer</div>}
        />,
      )

      const iframe = screen.getByTitle('Archived Page') as HTMLIFrameElement
      expect(iframe).toBeInTheDocument()
      expect(iframe.src).toContain(`/api/archived-pages/${sourceResponse.archived_page.id}/html`)
    })

    it('accept/reject toggles work per politician', () => {
      render(
        <EvaluationView
          politicians={sourceResponse.politicians}
          footer={() => <div>Footer</div>}
        />,
      )

      const acceptButtons = screen.getAllByRole('button', { name: /accept/i })
      expect(acceptButtons.length).toBe(3)

      fireEvent.click(acceptButtons[0])

      const rejectButtons = screen.getAllByRole('button', { name: /reject/i })
      expect(rejectButtons.length).toBe(3)
    })

    it('renders footer', () => {
      render(
        <EvaluationView
          politicians={sourceResponse.politicians}
          footer={() => <div data-testid="test-footer">Custom Footer</div>}
        />,
      )

      expect(screen.getByTestId('test-footer')).toBeInTheDocument()
      expect(screen.getByText('Custom Footer')).toBeInTheDocument()
    })
  })
})
