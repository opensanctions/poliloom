import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent, render } from '@testing-library/react'
import '@/test/highlight-mocks'
import { EvaluationView } from './EvaluationView'
import type { Politician, SourceResponse } from '@/types'
import { PropertyType } from '@/types'

vi.mock('@/contexts/UserPreferencesContext', () => ({
  useUserPreferences: () => ({
    isAdvancedMode: false,
  }),
}))

const source1: SourceResponse = {
  id: 'archived-1',
  url: 'https://en.wikipedia.org/wiki/Test',
  url_hash: 'abc',
  fetch_timestamp: '2024-01-01T00:00:00Z',
  status: 'done',
}

const source2: SourceResponse = {
  id: 'archived-2',
  url: 'https://gov.example.com/official',
  url_hash: 'def',
  fetch_timestamp: '2024-02-01T00:00:00Z',
  status: 'done',
}

const source3: SourceResponse = {
  id: 'archived-3',
  url: 'https://news.example.com/bio',
  url_hash: 'ghi',
  fetch_timestamp: '2024-03-01T00:00:00Z',
  status: 'done',
}

const politicianWithDifferentSources: Politician = {
  id: 'pol-1',
  name: 'Multi-Source Politician',
  wikidata_id: 'Q100',
  sources: [source1, source2, source3],
  properties: [
    {
      id: 'prop-1',
      type: PropertyType.P569,
      value: '+1975-06-15T00:00:00Z',
      value_precision: 11,
      statement_id: null,
      sources: [{ id: 'ref-1', source: source1, supporting_quotes: ['born June 15'] }],
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
      sources: [
        {
          id: 'ref-2',
          source: source2,
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
      sources: [
        {
          id: 'ref-3',
          source: source3,
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
  sources: [source1],
  properties: [
    {
      id: 'prop-wikidata',
      type: PropertyType.P569,
      value: '+1980-01-01T00:00:00Z',
      value_precision: 11,
      statement_id: 'Q101$some-uuid',
      sources: [{ id: 'ref-w', source: source1, supporting_quotes: ['born 1980'] }],
    },
    {
      id: 'prop-extracted',
      type: PropertyType.P569,
      value: '+1980-01-02T00:00:00Z',
      value_precision: 11,
      statement_id: null,
      sources: [{ id: 'ref-e', source: source1, supporting_quotes: ['born Jan 2'] }],
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
      sources: [],
    },
    {
      id: 'birth-wikidata',
      type: PropertyType.P19,
      entity_id: 'Q500',
      entity_name: 'Test City',
      statement_id: 'Q500$some-uuid',
      sources: [],
    },
  ],
}

const sourcePoliticians: Politician[] = [
  {
    id: 'pol-a',
    name: 'Source Politician A',
    wikidata_id: 'Q111',
    sources: [source1],
    properties: [
      {
        id: 'sp-1',
        type: PropertyType.P569,
        value: '+1970-01-01T00:00:00Z',
        value_precision: 11,
        statement_id: null,
        sources: [{ id: 'sr-1', source: source1, supporting_quotes: ['born 1970'] }],
      },
      {
        id: 'sp-2',
        type: PropertyType.P39,
        entity_id: 'Q555',
        entity_name: 'Mayor of Test City',
        statement_id: null,
        sources: [
          {
            id: 'sr-2',
            source: source1,
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
    sources: [source1],
    properties: [
      {
        id: 'sp-3',
        type: PropertyType.P27,
        entity_id: 'Q142',
        entity_name: 'France',
        statement_id: null,
        sources: [
          {
            id: 'sr-3',
            source: source1,
            supporting_quotes: ['French citizen'],
          },
        ],
      },
    ],
  },
]

describe('EvaluationView', () => {
  beforeEach(() => {
    CSS.highlights.clear()
  })

  describe('single politician - source handling', () => {
    it('auto-loads the first property with a source on mount', () => {
      render(
        <EvaluationView
          politicians={[politicianWithDifferentSources]}
          sourcesApiPath="/api/sources"
          footer={() => <div>Footer</div>}
        />,
      )

      const iframe = screen.getByTitle('Source') as HTMLIFrameElement
      expect(iframe).toBeInTheDocument()
      expect(iframe.src).toContain(`/api/sources/${source1.id}/html`)

      const viewButtons = screen.getAllByRole('button', { name: /• View|• Viewing/ })
      expect(viewButtons[0]).toHaveTextContent('• Viewing')
    })

    it('clicking View on a property updates the iframe to show that source', () => {
      render(
        <EvaluationView
          politicians={[politicianWithDifferentSources]}
          sourcesApiPath="/api/sources"
          footer={() => <div>Footer</div>}
        />,
      )

      const iframe = screen.getByTitle('Source') as HTMLIFrameElement
      expect(iframe.src).toContain(`/api/sources/${source1.id}/html`)

      const viewButtons = screen.getAllByRole('button', { name: /• View|• Viewing/ })
      const secondViewButton = viewButtons.find((btn) => btn.textContent === '• View')
      expect(secondViewButton).toBeDefined()
      fireEvent.click(secondViewButton!)

      expect(iframe.src).toContain(`/api/sources/${source2.id}/html`)
      expect(secondViewButton).toHaveTextContent('• Viewing')
    })

    it('switching between properties with different sources updates the iframe', () => {
      render(
        <EvaluationView
          politicians={[politicianWithDifferentSources]}
          sourcesApiPath="/api/sources"
          footer={() => <div>Footer</div>}
        />,
      )

      const iframe = screen.getByTitle('Source') as HTMLIFrameElement
      expect(iframe.src).toContain(`/api/sources/${source1.id}/html`)

      const viewButtons = screen.getAllByRole('button', { name: /• View|• Viewing/ })
      expect(viewButtons.length).toBe(3)

      fireEvent.click(viewButtons[1])
      expect(iframe.src).toContain(`/api/sources/${source2.id}/html`)

      fireEvent.click(viewButtons[2])
      expect(iframe.src).toContain(`/api/sources/${source3.id}/html`)

      fireEvent.click(viewButtons[0])
      expect(iframe.src).toContain(`/api/sources/${source1.id}/html`)
    })

    it('only the active property View button shows "Viewing"', () => {
      render(
        <EvaluationView
          politicians={[politicianWithDifferentSources]}
          sourcesApiPath="/api/sources"
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

    it('does not show View button for Wikidata statements even if they have sources', () => {
      render(
        <EvaluationView
          politicians={[politicianWithEdgeCases]}
          sourcesApiPath="/api/sources"
          footer={() => <div>Footer</div>}
        />,
      )

      const viewButtons = screen.getAllByRole('button', { name: /• View|• Viewing/ })
      expect(viewButtons.length).toBe(1)
    })
  })

  describe('multiple politicians', () => {
    it('renders multiple politicians with headers', () => {
      render(<EvaluationView politicians={sourcePoliticians} footer={() => <div>Footer</div>} />)

      expect(screen.getByText('Source Politician A')).toBeInTheDocument()
      expect(screen.getByText('Source Politician B')).toBeInTheDocument()
    })

    it('renders properties for each politician', () => {
      render(<EvaluationView politicians={sourcePoliticians} footer={() => <div>Footer</div>} />)

      expect(screen.getByText('Birth Date')).toBeInTheDocument()
      expect(screen.getByText('Mayor of Test City')).toBeInTheDocument()
      expect(screen.getByText('France')).toBeInTheDocument()
    })

    it('auto-loads the first source on mount', () => {
      render(
        <EvaluationView
          politicians={sourcePoliticians}
          sourcesApiPath="/api/sources"
          footer={() => <div>Footer</div>}
        />,
      )

      const iframe = screen.getByTitle('Source') as HTMLIFrameElement
      expect(iframe).toBeInTheDocument()
      expect(iframe.src).toContain(`/api/sources/${source1.id}/html`)
    })

    it('accept/reject toggles work per politician', () => {
      render(<EvaluationView politicians={sourcePoliticians} footer={() => <div>Footer</div>} />)

      const acceptButtons = screen.getAllByRole('button', { name: /accept/i })
      expect(acceptButtons.length).toBe(3)

      fireEvent.click(acceptButtons[0])

      const rejectButtons = screen.getAllByRole('button', { name: /reject/i })
      expect(rejectButtons.length).toBe(3)
    })

    it('renders footer', () => {
      render(
        <EvaluationView
          politicians={sourcePoliticians}
          footer={() => <div data-testid="test-footer">Custom Footer</div>}
        />,
      )

      expect(screen.getByTestId('test-footer')).toBeInTheDocument()
      expect(screen.getByText('Custom Footer')).toBeInTheDocument()
    })
  })
})
