import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent, waitFor, render, within, act } from '@testing-library/react'
import '@/test/mocks'
import { mockRouterPush, mockRouterRefresh, mockFetch, mockUseFilters } from '@/test/mocks'
import { PoliticianEvaluation } from './PoliticianEvaluation'
import type {
  Action,
  ActionEvidence,
  Politician,
  RestSnak,
  RestStatement,
  RestValue,
  SourceResponse,
  SourceStatusEvent,
  Statement,
  StatementFact,
  TermMaps,
} from '@/types'

const mockUseEventStream = vi.fn()
vi.mock('@/contexts/EventStreamContext', () => ({
  useEventStream: (...args: unknown[]) => mockUseEventStream(...args),
}))

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

const startTimeQualifier = (time: string): RestSnak => ({
  property: { id: 'P580' },
  value: timeContent(time),
})

const testSource: SourceResponse = {
  id: 'archived-1',
  url: 'https://en.wikipedia.org/wiki/Test',
  url_hash: 'abc',
  fetch_timestamp: '2024-01-01T00:00:00Z',
  status: 'done',
  language_qids: [],
}

const testEvidence: ActionEvidence = {
  id: 'ev-1',
  source: testSource,
  supporting_quotes: ['born on January 1, 1970'],
}

function fact(propertyId: string, value: RestValue, qualifiers: RestSnak[] = []): StatementFact {
  return { property: { id: propertyId }, value, qualifiers }
}

function createAction(
  id: string,
  propertyId: string,
  value: RestValue,
  options: {
    qualifiers?: RestSnak[]
    entityTerms?: TermMaps | null
    evidence?: ActionEvidence[]
    groupKey?: string
  } = {},
): Action {
  return {
    id,
    target_wikidata_statement_id: null,
    before: null,
    after: fact(propertyId, value, options.qualifiers ?? []),
    references_to_add: [],
    group_key: options.groupKey ?? id,
    change: 'add',
    entity_terms: options.entityTerms ?? null,
    evidence: options.evidence ?? [],
  }
}

function refineAction(
  id: string,
  statementId: string,
  before: StatementFact,
  after: StatementFact,
  options: { entityTerms?: TermMaps | null; evidence?: ActionEvidence[]; groupKey?: string } = {},
): Action {
  return {
    id,
    target_wikidata_statement_id: statementId,
    before,
    after,
    references_to_add: [],
    group_key: options.groupKey ?? id,
    change: 'refine',
    entity_terms: options.entityTerms ?? null,
    evidence: options.evidence ?? [],
  }
}

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

const politician: Politician = {
  id: 'pol-1',
  wikidata_id: 'Q987654',
  terms: terms({ en: 'Test Politician' }),
  sources: [testSource],
  statements: [
    makeStatement('stmt-1', 'P569', timeContent('+1970-01-01T00:00:00Z')),
    makeStatement('stmt-2', 'P39', entityContent('Q555'), {
      qualifiers: [startTimeQualifier('+2020-01-01T00:00:00Z')],
      entityTerms: terms({ en: 'Mayor of Test City' }),
    }),
  ],
  actions: [
    createAction('action-1', 'P19', entityContent('Q123'), {
      entityTerms: terms({ en: 'Test City' }),
      evidence: [{ id: 'ev-2', source: testSource, supporting_quotes: ['was born in Test City'] }],
    }),
    createAction('action-2', 'P27', entityContent('Q142'), {
      entityTerms: terms({ en: 'France' }),
      evidence: [{ id: 'ev-3', source: testSource, supporting_quotes: ['French politician'] }],
    }),
    refineAction(
      'action-3',
      'stmt-2',
      fact('P39', entityContent('Q555'), [startTimeQualifier('+2020-01-01T00:00:00Z')]),
      fact('P39', entityContent('Q555'), [startTimeQualifier('+2021-01-01T00:00:00Z')]),
      { evidence: [{ id: 'ev-4', source: testSource, supporting_quotes: ['mayor since 2021'] }] },
    ),
  ],
}

function mockApiResponse(body: unknown, ok = true) {
  return Promise.resolve({ ok, json: async () => body } as Response)
}

function boxContaining(text: string): HTMLElement {
  const box = screen.getByText(text).closest('div.bg-surface')
  if (!box) throw new Error(`No box contains ${text}`)
  return box as HTMLElement
}

describe('PoliticianEvaluation', () => {
  beforeEach(() => {
    CSS.highlights.clear()
    mockFetch.mockImplementation((url, options) => {
      if (options?.method === 'PATCH') {
        return mockApiResponse({ success: true, message: 'OK', errors: [] })
      }
      if (options?.method === 'POST') {
        return mockApiResponse({ wikidata_id: 'Q12345' })
      }
      return mockApiResponse(politician)
    })
  })

  it('renders the politician name from terms and the wikidata id', () => {
    render(<PoliticianEvaluation politician={politician} />)

    expect(screen.getByText('Test Politician')).toBeInTheDocument()
    expect(screen.getByText('(Q987654)')).toBeInTheDocument()
  })

  it('renders statements as current Wikidata context', () => {
    render(<PoliticianEvaluation politician={politician} />)

    expect(screen.getByText('Dates')).toBeInTheDocument()
    expect(screen.getByText('Birth Date')).toBeInTheDocument()
    expect(screen.getByText('January 1, 1970')).toBeInTheDocument()
    expect(screen.getByText('Political Positions')).toBeInTheDocument()
    expect(screen.getByText(/Mayor of Test City/)).toBeInTheDocument()
  })

  it('renders create and edit actions with evidence quotes', () => {
    render(<PoliticianEvaluation politician={politician} />)

    expect(screen.getByText('Birthplaces')).toBeInTheDocument()
    expect(screen.getByText('Citizenships')).toBeInTheDocument()
    expect(screen.getByText('"was born in Test City"')).toBeInTheDocument()
    expect(screen.getByText('"French politician"')).toBeInTheDocument()
    expect(
      screen.getByText(
        (_, element) =>
          element?.textContent === 'January 1, 2020 – present → January 1, 2021 – present',
      ),
    ).toBeInTheDocument()
  })

  it('allows users to decide actions by accepting or discarding', () => {
    render(<PoliticianEvaluation politician={politician} />)

    const acceptButton = screen.getAllByText('✓ Accept')[0]
    fireEvent.click(acceptButton)
    expect(acceptButton).toHaveAttribute('class', expect.stringContaining('bg-success '))

    const discardButton = screen.getAllByText('× Discard')[0]
    fireEvent.click(discardButton)
    expect(discardButton).toHaveAttribute('class', expect.stringContaining('bg-danger '))
  })

  it('preserves local decisions when refreshed politician props arrive', () => {
    const { rerender } = render(<PoliticianEvaluation politician={politician} />)

    const acceptButton = screen.getAllByText('✓ Accept')[0]
    fireEvent.click(acceptButton)
    rerender(<PoliticianEvaluation politician={{ ...politician }} />)

    expect(acceptButton).toHaveAttribute('class', expect.stringContaining('bg-success '))
  })

  it('shows "Skip Politician" when no decisions and "Submit Decisions & Next" when decisions exist', () => {
    render(<PoliticianEvaluation politician={politician} />)

    expect(screen.getByText('Skip Politician')).toBeInTheDocument()
    expect(screen.queryByText('Submit Decisions & Next')).not.toBeInTheDocument()

    fireEvent.click(screen.getAllByText('✓ Accept')[0])

    expect(screen.getByText('Submit Decisions & Next')).toBeInTheDocument()
    expect(screen.queryByText('Skip Politician')).not.toBeInTheDocument()
  })

  it('submits decisions via the actions endpoint and navigates to the next politician', async () => {
    render(<PoliticianEvaluation politician={politician} />)

    fireEvent.click(
      within(boxContaining('"was born in Test City"')).getByRole('button', { name: /✓ Accept/ }),
    )
    fireEvent.click(
      within(boxContaining('"French politician"')).getByRole('button', { name: /× Discard/ }),
    )

    fireEvent.click(screen.getByText('Submit Decisions & Next'))

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/politicians/Q987654',
        expect.objectContaining({
          method: 'PATCH',
        }),
      )
    })

    const patchCall = mockFetch.mock.calls.find(
      (call) => typeof call[0] === 'string' && call[0] === '/api/politicians/Q987654',
    )!
    expect(JSON.parse(patchCall[1]!.body as string)).toEqual({
      actions: [
        { id: 'action-1', is_accepted: true },
        { id: 'action-2', is_accepted: false },
      ],
      skips: ['action-3'],
    })

    expect(mockFetch).toHaveBeenCalledWith('/api/politicians/claim', { method: 'POST' })
    expect(mockFetch.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1)
    expect(mockRouterPush).toHaveBeenCalledWith('/politician/Q12345')
  })

  it('skips all undecided actions when skipping the politician', async () => {
    render(<PoliticianEvaluation politician={politician} />)

    fireEvent.click(screen.getByText('Skip Politician'))

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/politicians/Q987654',
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({
            actions: [],
            skips: ['action-1', 'action-2', 'action-3'],
          }),
        }),
      )
      expect(mockFetch).toHaveBeenCalledWith('/api/politicians/claim', { method: 'POST' })
      expect(mockFetch.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(
        1,
      )
      expect(mockRouterPush).toHaveBeenCalledWith('/politician/Q12345')
    })
  })

  it('uses current language and country filters when claiming after submission', async () => {
    mockUseFilters.mockReturnValue({
      languageQids: ['Q1860', 'Q188'],
      countryQids: ['Q30'],
      setLanguages: vi.fn(),
      setCountries: vi.fn(),
    })

    render(<PoliticianEvaluation politician={politician} />)
    fireEvent.click(screen.getAllByText('✓ Accept')[0])
    fireEvent.click(screen.getByText('Submit Decisions & Next'))

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/politicians/claim?languages=Q1860&languages=Q188&countries=Q30',
        { method: 'POST' },
      )
    })
  })

  it.each([
    { success: false, message: 'Action not claimed', errors: ['boom'] },
    { success: true, message: 'Processed with errors', errors: ['could not apply action-1'] },
  ])('shows application errors and waits for an explicit next: $message', async (result) => {
    mockFetch.mockImplementation((url, options) => {
      if (options?.method === 'PATCH') {
        return mockApiResponse(result)
      }
      if (options?.method === 'POST') {
        return mockApiResponse({ wikidata_id: 'Q12345' })
      }
      return mockApiResponse(politician)
    })

    render(<PoliticianEvaluation politician={politician} />)
    fireEvent.click(screen.getAllByText('✓ Accept')[0])
    fireEvent.click(screen.getByText('Submit Decisions & Next'))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(result.errors[0])
    })
    expect(mockRouterPush).not.toHaveBeenCalled()
    expect(screen.queryByText('Submit Decisions & Next')).not.toBeInTheDocument()

    // The decided id is not offered for resubmission.
    expect(screen.queryByText('✓ Accepted')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Next Politician' }))
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith('/api/politicians/claim', { method: 'POST' })
      expect(mockRouterPush).toHaveBeenCalledWith('/politician/Q12345')
    })
  })

  it('does not claim work when entering, changing, or leaving politician routes', () => {
    const { rerender, unmount } = render(<PoliticianEvaluation politician={politician} />)

    rerender(<PoliticianEvaluation politician={{ ...politician, wikidata_id: 'Q111111' }} />)
    unmount()

    expect(mockFetch).not.toHaveBeenCalled()
    expect(mockRouterPush).not.toHaveBeenCalled()
  })

  it('allows skipping while sources are processing without actions', async () => {
    const processing: Politician = {
      ...politician,
      sources: [{ ...testSource, status: 'processing' }],
      actions: [],
    }
    render(<PoliticianEvaluation politician={processing} />)

    expect(
      screen.queryByText(
        'Source ingestion is in progress. Review items will appear automatically.',
      ),
    ).not.toBeInTheDocument()
    const skip = screen.getByRole('button', { name: 'Skip Politician' })
    expect(skip).not.toBeDisabled()
    fireEvent.click(skip)

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/politicians/Q987654',
        expect.objectContaining({ method: 'PATCH' }),
      )
    })
  })

  it('shows newly extracted actions after a source-status refresh', async () => {
    const processing: Politician = {
      ...politician,
      sources: [{ ...testSource, status: 'processing' }],
      actions: [],
    }
    const { rerender } = render(<PoliticianEvaluation politician={processing} />)

    const handler = mockUseEventStream.mock.calls.find(
      ([eventType]) => eventType === 'source_status',
    )?.[1] as (event: SourceStatusEvent) => Promise<void>
    await act(async () => {
      await handler({
        type: 'source_status',
        politician_ids: [processing.id],
        source_id: testSource.id,
        status: 'done',
      })
    })
    rerender(<PoliticianEvaluation politician={politician} />)

    expect(mockRouterRefresh).toHaveBeenCalledOnce()
    expect(mockFetch).not.toHaveBeenCalledWith('/api/politicians/Q987654')
    expect(screen.getByText('Birthplaces')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Skip Politician' })).not.toBeDisabled()
    expect(
      screen.queryByText(
        'Source ingestion is in progress. Review items will appear automatically.',
      ),
    ).not.toBeInTheDocument()
    expect(mockFetch.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(0)
  })

  it('selects the source that finished ingesting when no source is selected', async () => {
    const processing: Politician = {
      ...politician,
      sources: [{ ...testSource, status: 'processing' }],
      actions: [],
    }
    const { rerender } = render(<PoliticianEvaluation politician={processing} />)

    expect(screen.getByText('Select a Source')).toBeInTheDocument()

    const handler = mockUseEventStream.mock.calls.find(
      ([eventType]) => eventType === 'source_status',
    )?.[1] as (event: SourceStatusEvent) => Promise<void>
    await act(async () => {
      await handler({
        type: 'source_status',
        politician_ids: [processing.id],
        source_id: testSource.id,
        status: 'done',
      })
    })
    rerender(<PoliticianEvaluation politician={politician} />)

    await waitFor(() => {
      expect(screen.getByTitle('Source')).toHaveAttribute(
        'src',
        `/api/sources/${testSource.id}/html`,
      )
    })
  })

  it('keeps the current selection when another source finishes ingesting', async () => {
    const otherSource: SourceResponse = {
      ...testSource,
      id: 'archived-2',
      url: 'https://example.org/',
    }
    const { rerender } = render(<PoliticianEvaluation politician={politician} />)

    const handler = mockUseEventStream.mock.calls.find(
      ([eventType]) => eventType === 'source_status',
    )?.[1] as (event: SourceStatusEvent) => Promise<void>
    await act(async () => {
      await handler({
        type: 'source_status',
        politician_ids: [politician.id],
        source_id: otherSource.id,
        status: 'done',
      })
    })
    rerender(
      <PoliticianEvaluation politician={{ ...politician, sources: [testSource, otherSource] }} />,
    )

    expect(screen.getByTitle('Source')).toHaveAttribute('src', `/api/sources/${testSource.id}/html`)
  })
})

describe('PoliticianEvaluation - no next politician', () => {
  beforeEach(() => {
    mockFetch.mockImplementation((url, options) => {
      if (options?.method === 'PATCH') {
        return mockApiResponse({ success: true, message: 'OK', errors: [] })
      }
      if (options?.method === 'POST') {
        return mockApiResponse({ wikidata_id: null })
      }
      return mockApiResponse(politician)
    })
  })

  it('returns home on submit when no next politician is available', async () => {
    render(<PoliticianEvaluation politician={politician} />)

    fireEvent.click(screen.getAllByText('✓ Accept')[0])
    fireEvent.click(screen.getByText('Submit Decisions & Next'))

    await waitFor(() => {
      expect(mockRouterPush).toHaveBeenCalledWith('/?empty=1')
    })
  })

  it('skips all pending actions when skipping with no next politician', async () => {
    render(<PoliticianEvaluation politician={politician} />)

    fireEvent.click(screen.getByText('Skip Politician'))

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/politicians/Q987654',
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({
            actions: [],
            skips: ['action-1', 'action-2', 'action-3'],
          }),
        }),
      )
      expect(mockRouterPush).toHaveBeenCalledWith('/?empty=1')
    })
  })
})
