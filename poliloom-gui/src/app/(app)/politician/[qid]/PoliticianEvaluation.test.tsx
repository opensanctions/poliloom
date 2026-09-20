import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent, waitFor, render, within } from '@testing-library/react'
import '@/test/mocks'
import {
  mockRouterPush,
  mockFetch,
  mockUseNextPoliticianContext,
  mockUseFilters,
  defaultNextPolitician,
} from '@/test/mocks'
import { PoliticianEvaluation } from './PoliticianEvaluation'
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

function createAction(
  id: string,
  propertyId: string,
  value: RestValue,
  options: {
    qualifiers?: RestSnak[]
    entityTerms?: TermMaps | null
    evidence?: ActionEvidence[]
  } = {},
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
    evidence: options.evidence ?? [],
    is_accepted: null,
    applied_at: null,
    error: null,
  }
}

function editAction(
  id: string,
  statementId: string,
  patch: JsonPatchOperation[],
  options: { entityTerms?: TermMaps | null; evidence?: ActionEvidence[] } = {},
): Action {
  return {
    id,
    kind: 'EDIT_STATEMENT',
    statement_id: statementId,
    payload: { patch },
    entity_terms: options.entityTerms ?? null,
    evidence: options.evidence ?? [],
    is_accepted: null,
    applied_at: null,
    error: null,
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
    editAction(
      'action-3',
      'stmt-2',
      [
        { op: 'test', path: '/qualifiers/0', value: startTimeQualifier('+2020-01-01T00:00:00Z') },
        {
          op: 'replace',
          path: '/qualifiers/0',
          value: startTimeQualifier('+2021-01-01T00:00:00Z'),
        },
      ],
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
      if (url === '/api/languages') {
        return mockApiResponse([
          {
            wikidata_id: 'Q1860',
            terms: terms({ en: 'English' }),
            wikimedia_code: 'en',
            sources_count: 1,
          },
        ])
      }
      if (options?.method === 'PATCH') {
        return mockApiResponse({ success: true, message: 'OK', errors: [] })
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

    expect(screen.getByText('Properties')).toBeInTheDocument()
    expect(screen.getByText('Birth Date')).toBeInTheDocument()
    expect(screen.getByText('January 1, 1970')).toBeInTheDocument()
    expect(screen.getByText('Political Positions')).toBeInTheDocument()
    expect(screen.getByText(/Mayor of Test City/)).toBeInTheDocument()
    expect(screen.getAllByText('Existing data').length).toBe(2)
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
          element?.textContent === 'Qualifier P580: January 1, 2020 → January 1, 2021',
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
      decisions: [
        { id: 'action-1', is_accepted: true },
        { id: 'action-2', is_accepted: false },
      ],
      skips: ['action-3'],
    })

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
            decisions: [],
            skips: ['action-1', 'action-2', 'action-3'],
          }),
        }),
      )
      expect(mockRouterPush).toHaveBeenCalledWith('/politician/Q12345')
    })
  })

  it('preserves language filters when refetching after submission', async () => {
    mockUseFilters.mockReturnValue({
      languageQids: ['Q1860', 'Q188'],
      countryQids: [],
      setLanguages: vi.fn(),
      setCountries: vi.fn(),
    })

    render(<PoliticianEvaluation politician={politician} />)
    fireEvent.click(screen.getAllByText('✓ Accept')[0])
    fireEvent.click(screen.getByText('Submit Decisions & Next'))

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/politicians/Q987654?languages=Q1860&languages=Q188',
      )
    })
  })

  it('surfaces submission errors from the backend', async () => {
    const alertMock = vi.spyOn(window, 'alert').mockImplementation(() => {})
    mockFetch.mockImplementation((url, options) => {
      if (url === '/api/languages') {
        return mockApiResponse([
          {
            wikidata_id: 'Q1860',
            terms: terms({ en: 'English' }),
            wikimedia_code: 'en',
            sources_count: 1,
          },
        ])
      }
      if (options?.method === 'PATCH') {
        return mockApiResponse({ success: false, message: 'Action not claimed', errors: ['boom'] })
      }
      return mockApiResponse(politician)
    })

    render(<PoliticianEvaluation politician={politician} />)
    fireEvent.click(screen.getAllByText('✓ Accept')[0])
    fireEvent.click(screen.getByText('Submit Decisions & Next'))

    await waitFor(() => {
      expect(alertMock).toHaveBeenCalledWith('Error submitting decisions: Action not claimed')
    })
    expect(mockRouterPush).not.toHaveBeenCalled()
    alertMock.mockRestore()
  })
})

describe('PoliticianEvaluation - no next politician', () => {
  beforeEach(() => {
    mockUseNextPoliticianContext.mockReturnValue({
      ...defaultNextPolitician,
      nextHref: '/session/enriching',
      politicianReady: false,
    })
    mockFetch.mockImplementation((url, options) => {
      if (url === '/api/languages') {
        return mockApiResponse([
          {
            wikidata_id: 'Q1860',
            terms: terms({ en: 'English' }),
            wikimedia_code: 'en',
            sources_count: 1,
          },
        ])
      }
      if (options?.method === 'PATCH') {
        return mockApiResponse({ success: true, message: 'OK', errors: [] })
      }
      return mockApiResponse(politician)
    })
  })

  it('navigates to /session/enriching on submit when no next politician is available', async () => {
    render(<PoliticianEvaluation politician={politician} />)

    fireEvent.click(screen.getAllByText('✓ Accept')[0])
    fireEvent.click(screen.getByText('Submit Decisions & Next'))

    await waitFor(() => {
      expect(mockRouterPush).toHaveBeenCalledWith('/session/enriching')
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
            decisions: [],
            skips: ['action-1', 'action-2', 'action-3'],
          }),
        }),
      )
      expect(mockRouterPush).toHaveBeenCalledWith('/session/enriching')
    })
  })
})
