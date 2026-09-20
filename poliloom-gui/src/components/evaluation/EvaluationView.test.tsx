import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useState, ComponentProps } from 'react'
import { screen, fireEvent, render, waitFor } from '@testing-library/react'
import '@/test/mocks'
import {
  EvaluationView,
  SourceSelection,
  findInitialSelection,
  findSelectionForSource,
} from './EvaluationView'
import type {
  Action,
  ActionEvidence,
  JsonPatchOperation,
  Politician,
  RestSnak,
  RestStatement,
  RestValue,
  SourceResponse,
  Statement,
  TermMaps,
} from '@/types'

type EvaluationViewProps = ComponentProps<typeof EvaluationView>
type WrapperProps = Omit<EvaluationViewProps, 'selection' | 'onSelectionChange'>

function ControlledEvaluationView(props: WrapperProps) {
  const [selection, setSelection] = useState<SourceSelection | null>(() =>
    findInitialSelection(props.politician, []),
  )
  return <EvaluationView {...props} selection={selection} onSelectionChange={setSelection} />
}

// --- Fixtures ---

const terms = (labels: Record<string, string>): TermMaps => ({
  labels,
  descriptions: {},
  aliases: {},
})

const timeContent = (time: string, precision = 11): RestValue => ({
  type: 'value',
  content: { time, precision, calendarmodel: 'http://www.wikidata.org/entity/Q1985727' },
})

const entityContent = (qid: string): RestValue => ({ type: 'value', content: qid })

const startTimeQualifier = (time: string, precision = 11): RestSnak => ({
  property: { id: 'P580' },
  value: timeContent(time, precision),
})

const endTimeQualifier = (time: string, precision = 11): RestSnak => ({
  property: { id: 'P582' },
  value: timeContent(time, precision),
})

function makeStatement(
  id: string,
  propertyId: string,
  value: RestValue,
  options: { qualifiers?: RestSnak[]; entityTerms?: TermMaps | null } = {},
): Statement {
  const document: RestStatement = {
    id,
    rank: 'normal',
    property: { id: propertyId },
    value,
    qualifiers: options.qualifiers ?? [],
    references: [],
  }
  return { id, document, entity_terms: options.entityTerms ?? null }
}

function evidence(
  id: string,
  source: SourceResponse,
  supportingQuotes: string[] | null,
): ActionEvidence {
  return { id, source, supporting_quotes: supportingQuotes }
}

function createAction(
  id: string,
  propertyId: string,
  value: RestValue,
  actionEvidence: ActionEvidence[],
  options: { qualifiers?: RestSnak[]; entityTerms?: TermMaps | null } = {},
): Action {
  return {
    id,
    kind: 'CREATE_STATEMENT',
    statement_id: null,
    payload: {
      statement: {
        rank: 'normal',
        property: { id: propertyId },
        value,
        qualifiers: options.qualifiers ?? [],
        references: [],
      },
    },
    entity_terms: options.entityTerms ?? null,
    evidence: actionEvidence,
    is_accepted: null,
    applied_at: null,
    error: null,
  }
}

function editAction(
  id: string,
  statementId: string,
  patch: JsonPatchOperation[],
  actionEvidence: ActionEvidence[] = [],
  options: { entityTerms?: TermMaps | null } = {},
): Action {
  return {
    id,
    kind: 'EDIT_STATEMENT',
    statement_id: statementId,
    payload: { patch },
    entity_terms: options.entityTerms ?? null,
    evidence: actionEvidence,
    is_accepted: null,
    applied_at: null,
    error: null,
  }
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
  wikidata_id: 'Q100',
  terms: terms({ en: 'Multi-Source Politician' }),
  sources: [source1, source2, source3],
  statements: [],
  actions: [
    createAction('action-1', 'P569', timeContent('+1975-06-15T00:00:00Z'), [
      evidence('ev-1', source1, ['born June 15']),
    ]),
    createAction(
      'action-2',
      'P39',
      entityContent('Q200'),
      [evidence('ev-2', source2, ['elected governor'])],
      {
        qualifiers: [startTimeQualifier('+2018-01-01T00:00:00Z')],
        entityTerms: terms({ en: 'Governor' }),
      },
    ),
    createAction(
      'action-3',
      'P19',
      entityContent('Q300'),
      [evidence('ev-3', source3, ['born in Capital City'])],
      { entityTerms: terms({ en: 'Capital City' }) },
    ),
  ],
}

const birthStatement = makeStatement('stmt-1', 'P569', timeContent('+1980-01-01T00:00:00Z'))

const positionStatement = makeStatement('stmt-2', 'P39', entityContent('Q400'), {
  qualifiers: [startTimeQualifier('+2020-01-01T00:00:00Z')],
  entityTerms: terms({ en: 'Mayor', sv: 'Borgmästare' }),
})

const birthplaceStatement = makeStatement('stmt-3', 'P19', entityContent('Q500'), {
  entityTerms: terms({ en: 'Test City' }),
})

const politicianWithStatements: Politician = {
  id: 'pol-2',
  wikidata_id: 'Q101',
  terms: terms({ en: 'Statement Politician' }),
  sources: [source1],
  statements: [birthStatement, positionStatement, birthplaceStatement],
  actions: [
    editAction(
      'edit-1',
      'stmt-1',
      [
        { op: 'test', path: '/value', value: timeContent('+1980-01-01T00:00:00Z') },
        { op: 'replace', path: '/value', value: timeContent('+1980-01-02T00:00:00Z') },
      ],
      [evidence('ev-e1', source1, ['born January 2'])],
    ),
  ],
}

describe('EvaluationView', () => {
  beforeEach(() => {
    CSS.highlights.clear()
  })

  describe('source handling', () => {
    it('auto-loads the first action evidence source on mount', () => {
      render(
        <ControlledEvaluationView
          politician={politicianWithDifferentSources}
          userLanguageCodes={[]}
          footer={() => <div>Footer</div>}
        />,
      )

      const iframe = screen.getByTitle('Source') as HTMLIFrameElement
      expect(iframe.src).toContain(`/api/sources/${source1.id}/html`)

      const viewButtons = screen.getAllByRole('button', { name: /• View|• Viewing/ })
      expect(viewButtons[0]).toHaveTextContent('• Viewing')
    })

    it('clicking View on an action updates the iframe to show that source', () => {
      render(
        <ControlledEvaluationView
          politician={politicianWithDifferentSources}
          userLanguageCodes={[]}
          footer={() => <div>Footer</div>}
        />,
      )

      const iframe = screen.getByTitle('Source') as HTMLIFrameElement
      expect(iframe.src).toContain(`/api/sources/${source1.id}/html`)

      const viewButtons = screen.getAllByRole('button', { name: /• View|• Viewing/ })
      const secondViewButton = viewButtons.find((btn) => btn.textContent === '• View')
      fireEvent.click(secondViewButton!)

      expect(iframe.src).toContain(`/api/sources/${source2.id}/html`)
      expect(secondViewButton).toHaveTextContent('• Viewing')
    })

    it('switching between actions with different sources updates the iframe', () => {
      render(
        <ControlledEvaluationView
          politician={politicianWithDifferentSources}
          userLanguageCodes={[]}
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

    it('only the active action View button shows "Viewing"', () => {
      render(
        <ControlledEvaluationView
          politician={politicianWithDifferentSources}
          userLanguageCodes={[]}
          footer={() => <div>Footer</div>}
        />,
      )

      const viewButtons = screen.getAllByRole('button', { name: /• View|• Viewing/ })

      expect(viewButtons[0]).toHaveTextContent('• Viewing')
      expect(viewButtons[1]).toHaveTextContent('• View')

      fireEvent.click(viewButtons[1])

      expect(viewButtons[0]).toHaveTextContent('• View')
      expect(viewButtons[1]).toHaveTextContent('• Viewing')
    })

    it('shows no source section for statements without actions', () => {
      render(
        <ControlledEvaluationView
          politician={politicianWithStatements}
          userLanguageCodes={[]}
          footer={() => <div>Footer</div>}
        />,
      )

      // Only the edit action has evidence; statements render no View buttons of their own.
      const viewButtons = screen.getAllByRole('button', { name: /• View|• Viewing/ })
      expect(viewButtons.length).toBe(1)
    })
  })

  describe('rendering statements and actions', () => {
    it('renders statements as current Wikidata context', () => {
      render(
        <ControlledEvaluationView
          politician={politicianWithStatements}
          userLanguageCodes={[]}
          footer={() => <div>Footer</div>}
        />,
      )

      expect(screen.getByText('Properties')).toBeInTheDocument()
      expect(screen.getByText('Birth Date')).toBeInTheDocument()
      expect(screen.getByText('January 1, 1980')).toBeInTheDocument()
      expect(screen.getAllByText('Existing data').length).toBe(3)
    })

    it('renders create actions as proposals with accept and discard buttons', () => {
      render(
        <ControlledEvaluationView
          politician={politicianWithDifferentSources}
          userLanguageCodes={[]}
          footer={() => <div>Footer</div>}
        />,
      )

      expect(screen.getByText('June 15, 1975')).toBeInTheDocument()
      expect(screen.getAllByText('New data 🎉').length).toBe(3)
      // The active source is source1, so only action-1's controls are live.
      expect(screen.getAllByRole('button', { name: /✓ Accept/ }).length).toBe(1)
      expect(screen.getAllByRole('button', { name: /× Discard/ }).length).toBe(1)
      expect(screen.getAllByText('View source to decide').length).toBe(2)
    })

    it('renders entity group titles with the best label in the user language', () => {
      render(
        <ControlledEvaluationView
          politician={politicianWithStatements}
          userLanguageCodes={['sv']}
          footer={() => <div>Footer</div>}
        />,
      )

      expect(screen.getByText(/Borgmästare/)).toBeInTheDocument()
    })

    it('falls back to the QID when an entity has no labels', () => {
      const politician: Politician = {
        ...politicianWithStatements,
        statements: [makeStatement('stmt-3', 'P19', entityContent('Q500'), { entityTerms: null })],
        actions: [],
      }

      render(
        <ControlledEvaluationView
          politician={politician}
          userLanguageCodes={[]}
          footer={() => <div>Footer</div>}
        />,
      )

      expect(screen.getByRole('link', { name: /Q500/ })).toBeInTheDocument()
    })

    it('renders edit actions next to their target statement using the patch', () => {
      render(
        <ControlledEvaluationView
          politician={politicianWithStatements}
          userLanguageCodes={[]}
          footer={() => <div>Footer</div>}
        />,
      )

      expect(
        screen.getByText(
          (_, element) => element?.textContent === 'Value: January 1, 1980 → January 2, 1980',
        ),
      ).toBeInTheDocument()
      expect(screen.getByText('"born January 2"')).toBeInTheDocument()
    })

    it('renders position timeframes from statement qualifiers', () => {
      render(
        <ControlledEvaluationView
          politician={politicianWithStatements}
          userLanguageCodes={[]}
          footer={() => <div>Footer</div>}
        />,
      )

      expect(screen.getByText('January 1, 2020 – present')).toBeInTheDocument()
    })
  })

  describe('decisions', () => {
    it('marks an action accepted when Accept is clicked and clears it when clicked again', () => {
      render(
        <ControlledEvaluationView
          politician={politicianWithDifferentSources}
          userLanguageCodes={[]}
          footer={() => <div>Footer</div>}
        />,
      )

      const acceptButton = screen.getAllByRole('button', { name: /✓ Accept/ })[0]
      fireEvent.click(acceptButton)
      expect(acceptButton).toHaveAttribute('class', expect.stringContaining('bg-success '))

      fireEvent.click(acceptButton)
      expect(acceptButton).not.toHaveAttribute('class', expect.stringContaining('bg-success '))
    })

    it('marks an action discarded when Discard is clicked', () => {
      render(
        <ControlledEvaluationView
          politician={politicianWithDifferentSources}
          userLanguageCodes={[]}
          footer={() => <div>Footer</div>}
        />,
      )

      const discardButton = screen.getAllByRole('button', { name: /× Discard/ })[0]
      fireEvent.click(discardButton)
      expect(discardButton).toHaveAttribute('class', expect.stringContaining('bg-danger '))
    })

    it('hides decision buttons until the action source is viewed', () => {
      const politician: Politician = {
        ...politicianWithDifferentSources,
        actions: [
          createAction('action-1', 'P569', timeContent('+1975-06-15T00:00:00Z'), [
            evidence('ev-1', source1, ['born June 15']),
          ]),
          createAction('action-1b', 'P570', timeContent('+2005-05-05T00:00:00Z'), [
            evidence('ev-1b', source1, ['died May 5']),
          ]),
          createAction('action-3', 'P19', entityContent('Q300'), [
            evidence('ev-3', source3, ['born in Capital City']),
          ]),
        ],
      }

      render(
        <ControlledEvaluationView
          politician={politician}
          userLanguageCodes={[]}
          footer={() => <div>Footer</div>}
        />,
      )

      // Source 1 is active; the two source-1 actions are live, the source-3 one is not.
      expect(screen.getAllByText('View source to decide').length).toBe(1)
      expect(screen.getAllByRole('button', { name: /✓ Accept/ }).length).toBe(2)

      const viewButtons = screen.getAllByRole('button', { name: /• View|• Viewing/ })
      fireEvent.click(viewButtons[2])

      expect(screen.getAllByText('View source to decide').length).toBe(2)
      expect(screen.getAllByRole('button', { name: /✓ Accept/ }).length).toBe(1)
    })

    it('submits decisions for decided actions and skips the undecided ones', async () => {
      const onSubmit = vi.fn().mockResolvedValue(undefined)
      render(
        <ControlledEvaluationView
          politician={politicianWithDifferentSources}
          userLanguageCodes={[]}
          onSubmit={onSubmit}
          footer={({ submit }) => <button onClick={submit}>Submit Decisions &amp; Next</button>}
        />,
      )

      fireEvent.click(screen.getAllByRole('button', { name: /✓ Accept/ })[0])

      // Decide action-2 after viewing its source.
      fireEvent.click(screen.getAllByRole('button', { name: /• View|• Viewing/ })[1])
      fireEvent.click(screen.getAllByRole('button', { name: /× Discard/ })[0])
      fireEvent.click(screen.getByRole('button', { name: /Submit Decisions & Next/ }))

      await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1))
      expect(onSubmit).toHaveBeenCalledWith({
        decisions: [
          { id: 'action-1', is_accepted: true },
          { id: 'action-2', is_accepted: false },
        ],
        skips: ['action-3'],
      })
    })
  })

  describe('add source', () => {
    it('shows "+ Add Source" button when onAddSource is provided', () => {
      render(
        <ControlledEvaluationView
          politician={politicianWithDifferentSources}
          userLanguageCodes={[]}
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
          userLanguageCodes={[]}
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
          userLanguageCodes={[]}
          footer={() => <div>Footer</div>}
          onAddSource={async () => {}}
        />,
      )

      expect(screen.queryByRole('button', { name: '+ Add Source' })).not.toBeInTheDocument()
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

  function makePolitician(actions: Action[]): Politician {
    return {
      id: 'p',
      wikidata_id: 'Q1',
      terms: terms({ en: 'Test' }),
      sources: [enSource, frSource],
      statements: [],
      actions,
    }
  }

  it('prefers action evidence whose source matches the user language', () => {
    const politician = makePolitician([
      createAction('a1', 'P569', timeContent('+1990-01-01T00:00:00Z'), [
        evidence('e1', enSource, ['en quote']),
      ]),
      createAction('a2', 'P570', timeContent('+1990-02-02T00:00:00Z'), [
        evidence('e2', frSource, ['fr quote']),
      ]),
    ])
    const selection = findInitialSelection(politician, ['Q150'])
    expect(selection?.source.id).toBe('src-fr')
    expect(selection?.quotes).toEqual(['fr quote'])
  })

  it('falls back to the first action with evidence when no language matches', () => {
    const politician = makePolitician([
      createAction('a1', 'P569', timeContent('+1990-01-01T00:00:00Z'), [
        evidence('e1', enSource, ['en quote']),
      ]),
    ])
    const selection = findInitialSelection(politician, ['Q150'])
    expect(selection?.source.id).toBe('src-en')
  })

  it('uses fallback when languageQids is empty', () => {
    const politician = makePolitician([
      createAction('a1', 'P569', timeContent('+1990-01-01T00:00:00Z'), [
        evidence('e1', enSource, ['en quote']),
      ]),
    ])
    const selection = findInitialSelection(politician, [])
    expect(selection?.source.id).toBe('src-en')
  })

  it('returns null when no action has evidence', () => {
    const politician = makePolitician([
      createAction('a1', 'P569', timeContent('+1990-01-01T00:00:00Z'), []),
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

  function makePolitician(actions: Action[]): Politician {
    return {
      id: 'p',
      wikidata_id: 'Q1',
      terms: terms({ en: 'Test' }),
      sources: [src],
      statements: [],
      actions,
    }
  }

  it('returns the source with quotes from the first matching action evidence', () => {
    const politician = makePolitician([
      createAction('a1', 'P569', timeContent('+1990-01-01T00:00:00Z'), [
        evidence('e1', otherSrc, ['skip']),
        evidence('e2', src, ['first match']),
      ]),
      createAction('a2', 'P570', timeContent('+2000-01-01T00:00:00Z'), [
        evidence('e3', src, ['second match']),
      ]),
    ])
    const selection = findSelectionForSource(politician, 'src-1')
    expect(selection?.source.id).toBe('src-1')
    expect(selection?.quotes).toEqual(['first match'])
  })

  it('returns the source with null quotes when no action evidence links to it', () => {
    const politician = makePolitician([])
    const selection = findSelectionForSource(politician, 'src-1')
    expect(selection?.source.id).toBe('src-1')
    expect(selection?.quotes).toBeNull()
  })

  it('returns null when the source is not in politician.sources', () => {
    const politician = makePolitician([])
    expect(findSelectionForSource(politician, 'unknown')).toBeNull()
  })
})
