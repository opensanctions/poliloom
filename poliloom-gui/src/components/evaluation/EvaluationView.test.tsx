import { describe, it, expect, beforeEach } from 'vitest'
import { useState, ComponentProps } from 'react'
import { screen, fireEvent, render } from '@testing-library/react'
import '@/test/mocks'
import {
  EvaluationView,
  SourceSelection,
  findInitialSelection,
  findSelectionForSource,
} from './EvaluationView'
import type { Politician, SourceResponse } from '@/types'
import { PropertyType } from '@/types'

type EvaluationViewProps = ComponentProps<typeof EvaluationView>
type WrapperProps = Omit<EvaluationViewProps, 'selection' | 'onSelectionChange'>

function ControlledEvaluationView(props: WrapperProps) {
  const [selection, setSelection] = useState<SourceSelection | null>(() =>
    findInitialSelection(props.politician, []),
  )
  return <EvaluationView {...props} selection={selection} onSelectionChange={setSelection} />
}

const source1: SourceResponse = {
  id: 'archived-1',
  url: 'https://en.wikipedia.org/wiki/Test',
  url_hash: 'abc',
  fetch_timestamp: '2024-01-01T00:00:00Z',
  status: 'done',
  language_qids: [],
}

const source2: SourceResponse = {
  id: 'archived-2',
  url: 'https://gov.example.com/official',
  url_hash: 'def',
  fetch_timestamp: '2024-02-01T00:00:00Z',
  status: 'done',
  language_qids: [],
}

const source3: SourceResponse = {
  id: 'archived-3',
  url: 'https://news.example.com/bio',
  url_hash: 'ghi',
  fetch_timestamp: '2024-03-01T00:00:00Z',
  status: 'done',
  language_qids: [],
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

describe('EvaluationView', () => {
  beforeEach(() => {
    CSS.highlights.clear()
  })

  describe('source handling', () => {
    it('auto-loads the first property with a source on mount', () => {
      render(
        <ControlledEvaluationView
          politician={politicianWithDifferentSources}
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
        <ControlledEvaluationView
          politician={politicianWithDifferentSources}
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
        <ControlledEvaluationView
          politician={politicianWithDifferentSources}
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
        <ControlledEvaluationView
          politician={politicianWithDifferentSources}
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
        <ControlledEvaluationView
          politician={politicianWithEdgeCases}
          sourcesApiPath="/api/sources"
          footer={() => <div>Footer</div>}
        />,
      )

      const viewButtons = screen.getAllByRole('button', { name: /• View|• Viewing/ })
      expect(viewButtons.length).toBe(1)
    })
  })

  describe('add source', () => {
    it('shows "+ Add Source" button when onAddSource is provided', () => {
      render(
        <ControlledEvaluationView
          politician={politicianWithDifferentSources}
          footer={() => <div>Footer</div>}
          onAddSource={async () => {}}
        />,
      )

      expect(screen.getByRole('button', { name: '+ Add Source' })).toBeInTheDocument()
    })

    it('does not show "+ Add Source" button when onAddSource is not provided', () => {
      render(
        <ControlledEvaluationView
          politician={politicianWithDifferentSources}
          footer={() => <div>Footer</div>}
        />,
      )

      expect(screen.queryByRole('button', { name: '+ Add Source' })).not.toBeInTheDocument()
    })

    it('does not show "+ Add Source" button when politician has no wikidata_id', () => {
      const politicianNoQid: Politician = {
        ...politicianWithDifferentSources,
        wikidata_id: null,
      }
      render(
        <ControlledEvaluationView
          politician={politicianNoQid}
          footer={() => <div>Footer</div>}
          onAddSource={async () => {}}
        />,
      )

      expect(screen.queryByRole('button', { name: '+ Add Source' })).not.toBeInTheDocument()
    })

    it('shows add source form when clicking "+ Add Source"', () => {
      render(
        <ControlledEvaluationView
          politician={politicianWithDifferentSources}
          footer={() => <div>Footer</div>}
          onAddSource={async () => {}}
        />,
      )

      fireEvent.click(screen.getByRole('button', { name: '+ Add Source' }))

      expect(screen.getByPlaceholderText('https://...')).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: '+ Add Source' })).not.toBeInTheDocument()
    })

    it('hides add source form when clicking "Cancel"', () => {
      render(
        <ControlledEvaluationView
          politician={politicianWithDifferentSources}
          footer={() => <div>Footer</div>}
          onAddSource={async () => {}}
        />,
      )

      fireEvent.click(screen.getByRole('button', { name: '+ Add Source' }))
      fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

      expect(screen.queryByPlaceholderText('https://...')).not.toBeInTheDocument()
      expect(screen.getByRole('button', { name: '+ Add Source' })).toBeInTheDocument()
    })
  })

  describe('advanced mode - add property', () => {
    it('shows add buttons when isAdvancedMode is true', () => {
      render(
        <ControlledEvaluationView
          politician={politicianWithDifferentSources}
          footer={() => <div>Footer</div>}
          isAdvancedMode={true}
        />,
      )

      expect(screen.getByText('+ Add Date')).toBeInTheDocument()
      expect(screen.getByText('+ Add Position')).toBeInTheDocument()
      expect(screen.getByText('+ Add Birthplace')).toBeInTheDocument()
    })

    it('hides add buttons when isAdvancedMode is false', () => {
      render(
        <ControlledEvaluationView
          politician={politicianWithDifferentSources}
          footer={() => <div>Footer</div>}
          isAdvancedMode={false}
        />,
      )

      expect(screen.queryByText('+ Add Date')).not.toBeInTheDocument()
      expect(screen.queryByText('+ Add Position')).not.toBeInTheDocument()
    })

    it('opens add form when add button is clicked', () => {
      render(
        <ControlledEvaluationView
          politician={politicianWithDifferentSources}
          footer={() => <div>Footer</div>}
          isAdvancedMode={true}
        />,
      )

      fireEvent.click(screen.getByText('+ Add Date'))

      // The add button should be replaced by the form
      expect(screen.queryByText('+ Add Date')).not.toBeInTheDocument()
    })
  })
})

describe('findInitialSelection', () => {
  const enSource: SourceResponse = {
    id: 'src-en',
    url: 'https://en.example.com',
    url_hash: 'h1',
    fetch_timestamp: '2024-01-01T00:00:00Z',
    status: 'done',
    language_qids: ['Q1860'],
  }
  const frSource: SourceResponse = {
    id: 'src-fr',
    url: 'https://fr.example.com',
    url_hash: 'h2',
    fetch_timestamp: '2024-01-01T00:00:00Z',
    status: 'done',
    language_qids: ['Q150'],
  }

  function makePolitician(props: Politician['properties']): Politician {
    return {
      id: 'p',
      name: 'Test',
      wikidata_id: 'Q1',
      sources: [enSource, frSource],
      properties: props,
    }
  }

  it('prefers a property whose first source matches the user language', () => {
    const politician = makePolitician([
      {
        id: 'p1',
        type: PropertyType.P569,
        value: '+1990-01-01T00:00:00Z',
        statement_id: null,
        sources: [{ id: 'r1', source: enSource, supporting_quotes: ['en quote'] }],
      },
      {
        id: 'p2',
        type: PropertyType.P570,
        value: '+1990-02-02T00:00:00Z',
        statement_id: null,
        sources: [{ id: 'r2', source: frSource, supporting_quotes: ['fr quote'] }],
      },
    ])
    const selection = findInitialSelection(politician, ['Q150'])
    expect(selection?.source.id).toBe('src-fr')
    expect(selection?.quotes).toEqual(['fr quote'])
  })

  it('falls back to the first non-statement property when no language matches', () => {
    const politician = makePolitician([
      {
        id: 'p1',
        type: PropertyType.P569,
        value: '+1990-01-01T00:00:00Z',
        statement_id: null,
        sources: [{ id: 'r1', source: enSource, supporting_quotes: ['en quote'] }],
      },
    ])
    const selection = findInitialSelection(politician, ['Q150'])
    expect(selection?.source.id).toBe('src-en')
  })

  it('uses fallback when languageQids is empty', () => {
    const politician = makePolitician([
      {
        id: 'p1',
        type: PropertyType.P569,
        value: '+1990-01-01T00:00:00Z',
        statement_id: null,
        sources: [{ id: 'r1', source: enSource, supporting_quotes: ['en quote'] }],
      },
    ])
    const selection = findInitialSelection(politician, [])
    expect(selection?.source.id).toBe('src-en')
  })

  it('skips statement properties even when they match by language', () => {
    const politician = makePolitician([
      {
        id: 'p1',
        type: PropertyType.P569,
        value: '+1990-01-01T00:00:00Z',
        statement_id: 'Q1$existing',
        sources: [{ id: 'r1', source: frSource, supporting_quotes: ['skip me'] }],
      },
      {
        id: 'p2',
        type: PropertyType.P570,
        value: '+2000-01-01T00:00:00Z',
        statement_id: null,
        sources: [{ id: 'r2', source: enSource, supporting_quotes: ['en'] }],
      },
    ])
    const selection = findInitialSelection(politician, ['Q150'])
    expect(selection?.source.id).toBe('src-en')
  })

  it('returns null when no non-statement property has sources', () => {
    const politician = makePolitician([
      {
        id: 'p1',
        type: PropertyType.P569,
        value: '+1990-01-01T00:00:00Z',
        statement_id: 'Q1$existing',
        sources: [{ id: 'r1', source: enSource, supporting_quotes: ['x'] }],
      },
    ])
    expect(findInitialSelection(politician, [])).toBeNull()
  })
})

describe('findSelectionForSource', () => {
  const src: SourceResponse = {
    id: 'src-1',
    url: 'https://example.com',
    url_hash: 'h',
    fetch_timestamp: '2024-01-01T00:00:00Z',
    status: 'done',
    language_qids: [],
  }
  const otherSrc: SourceResponse = {
    id: 'src-2',
    url: 'https://other.com',
    url_hash: 'h2',
    fetch_timestamp: '2024-01-01T00:00:00Z',
    status: 'done',
    language_qids: [],
  }

  it('returns the source with quotes from the first matching property ref', () => {
    const politician: Politician = {
      id: 'p',
      name: 'Test',
      wikidata_id: 'Q1',
      sources: [src],
      properties: [
        {
          id: 'p1',
          type: PropertyType.P569,
          value: '+1990-01-01T00:00:00Z',
          statement_id: null,
          sources: [
            { id: 'r1', source: otherSrc, supporting_quotes: ['skip'] },
            { id: 'r2', source: src, supporting_quotes: ['first match'] },
          ],
        },
        {
          id: 'p2',
          type: PropertyType.P570,
          value: '+2000-01-01T00:00:00Z',
          statement_id: null,
          sources: [{ id: 'r3', source: src, supporting_quotes: ['second match'] }],
        },
      ],
    }
    const selection = findSelectionForSource(politician, 'src-1')
    expect(selection?.source.id).toBe('src-1')
    expect(selection?.quotes).toEqual(['first match'])
  })

  it('returns the source with null quotes when present in politician.sources but no property links to it', () => {
    const politician: Politician = {
      id: 'p',
      name: 'Test',
      wikidata_id: 'Q1',
      sources: [src],
      properties: [],
    }
    const selection = findSelectionForSource(politician, 'src-1')
    expect(selection?.source.id).toBe('src-1')
    expect(selection?.quotes).toBeNull()
  })

  it('returns null when the source is not in politician.sources', () => {
    const politician: Politician = {
      id: 'p',
      name: 'Test',
      wikidata_id: 'Q1',
      sources: [],
      properties: [],
    }
    expect(findSelectionForSource(politician, 'unknown')).toBeNull()
  })
})
