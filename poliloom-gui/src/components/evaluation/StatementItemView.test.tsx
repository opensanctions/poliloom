import { render, screen, fireEvent } from '@testing-library/react'
import { beforeEach, vi } from 'vitest'
import { mockUseLabelLanguages } from '@/test/mocks'
import { StatementItemView } from './StatementItemView'
import type {
  Action,
  ActionEvidence,
  JsonPatchOperation,
  RestSnak,
  RestStatement,
  RestValue,
  SourceResponse,
  Statement,
  TermMaps,
} from '@/types'

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

const mockSource: SourceResponse = {
  id: 'archived-1',
  url: 'https://en.wikipedia.org/wiki/Test_Politician',
  url_hash: 'abc123',
  fetch_timestamp: '2024-01-01T00:00:00Z',
  status: 'done',
  language_qids: [],
}

const mockEvidence: ActionEvidence = {
  id: 'ev-1',
  source: mockSource,
  supporting_quotes: ['Test proof line'],
}

function statement(
  id: string,
  propertyId: string,
  value: RestValue,
  options: {
    qualifiers?: RestSnak[]
    references?: RestStatement['references']
    entityTerms?: TermMaps | null
  } = {},
): Statement {
  return {
    id,
    entity_terms: options.entityTerms ?? null,
    document: {
      id,
      rank: 'normal',
      property: { id: propertyId },
      value,
      qualifiers: options.qualifiers ?? [],
      references: options.references ?? [],
    },
  }
}

function createAction(
  id: string,
  propertyId: string,
  value: RestValue,
  options: {
    qualifiers?: RestSnak[]
    references?: RestStatement['references']
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
        references: options.references ?? [],
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

const baseProps = {
  decisions: {},
  onDecision: vi.fn(),
  activeSourceId: null as string | null,
}

beforeEach(() => {
  mockUseLabelLanguages.mockReturnValue(['sv'])
})

describe('StatementItemView - statements', () => {
  it('renders a birth date statement with formatted value', () => {
    render(
      <StatementItemView
        {...baseProps}
        item={{
          statement: statement('s1', 'P569', timeContent('+1990-05-15T00:00:00Z')),
          createAction: null,
          editActions: [],
        }}
      />,
    )

    expect(screen.getByText('May 15, 1990')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Accept/ })).not.toBeInTheDocument()
  })

  it('renders a position statement with date range from qualifiers', () => {
    render(
      <StatementItemView
        {...baseProps}
        item={{
          statement: statement('s1', 'P39', entityContent('Q400'), {
            qualifiers: [
              { property: { id: 'P580' }, value: timeContent('+2020-01-01T00:00:00Z') },
              { property: { id: 'P582' }, value: timeContent('+2024-12-31T00:00:00Z') },
            ],
          }),
          createAction: null,
          editActions: [],
        }}
      />,
    )

    expect(screen.getByText('January 1, 2020 – December 31, 2024')).toBeInTheDocument()
  })

  it('shows no timeframe message for position without date qualifiers', () => {
    render(
      <StatementItemView
        {...baseProps}
        item={{
          statement: statement('s1', 'P39', entityContent('Q400')),
          createAction: null,
          editActions: [],
        }}
      />,
    )

    expect(screen.getByText('No timeframe specified')).toBeInTheDocument()
  })

  it('does not render raw metadata for an existing statement', () => {
    render(
      <StatementItemView
        {...baseProps}
        item={{
          statement: statement('s1', 'P39', entityContent('Q400'), {
            qualifiers: [{ property: { id: 'P580' }, value: timeContent('+2020-01-01T00:00:00Z') }],
            references: [
              {
                hash: 'r1',
                parts: [{ property: { id: 'P854' }, value: entityContent('https://example.com') }],
              },
            ],
          }),
          createAction: null,
          editActions: [],
        }}
      />,
    )

    expect(screen.queryByRole('button', { name: 'Qualifiers' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'References (1)' })).not.toBeInTheDocument()
    expect(screen.queryByText(/"P580"/)).not.toBeInTheDocument()
    expect(screen.queryByText(/"P854"/)).not.toBeInTheDocument()
  })
})

describe('StatementItemView - create actions', () => {
  it('renders the proposal with evidence', () => {
    render(
      <StatementItemView
        {...baseProps}
        item={{
          statement: null,
          createAction: createAction('a1', 'P569', timeContent('+1990-05-15T00:00:00Z'), {
            evidence: [mockEvidence],
          }),
          editActions: [],
        }}
      />,
    )

    expect(screen.getByText('May 15, 1990')).toBeInTheDocument()
    expect(screen.getByText('"Test proof line"')).toBeInTheDocument()
  })

  it('renders the reference included in a create action', () => {
    render(
      <StatementItemView
        {...baseProps}
        item={{
          statement: null,
          createAction: createAction('a1', 'P19', entityContent('Q300'), {
            references: [
              {
                parts: [
                  {
                    property: { id: 'P854' },
                    value: { type: 'value', content: 'https://example.com/source' },
                  },
                  { property: { id: 'P143' }, value: entityContent('Q328') },
                ],
              },
            ],
          }),
          editActions: [],
        }}
      />,
    )

    expect(screen.getByText('+ Reference')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'https://example.com/source' })).toBeInTheDocument()
    expect(screen.getByText('Imported from')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Q328' })).toHaveAttribute(
      'href',
      'https://www.wikidata.org/wiki/Q328',
    )
  })

  it('calls onDecision when Accept and Discard are clicked', () => {
    const onDecision = vi.fn()
    const action = createAction('a1', 'P19', entityContent('Q300'), {
      entityTerms: terms({ sv: 'Svenska staden', en: 'English City' }),
      evidence: [mockEvidence],
    })

    render(
      <StatementItemView
        {...baseProps}
        onDecision={onDecision}
        activeSourceId={mockSource.id}
        item={{ statement: null, createAction: action, editActions: [] }}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: /✓ Accept/ }))
    expect(onDecision).toHaveBeenCalledWith(action, true)

    fireEvent.click(screen.getByRole('button', { name: /× Discard/ }))
    expect(onDecision).toHaveBeenCalledWith(action, false)
  })

  it('shows decided status text when the evidence source is not active', () => {
    render(
      <StatementItemView
        {...baseProps}
        decisions={{ a1: true }}
        item={{
          statement: null,
          createAction: createAction('a1', 'P19', entityContent('Q300'), {
            evidence: [mockEvidence],
          }),
          editActions: [],
        }}
      />,
    )

    expect(screen.getByText('✓ Accepted')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /✓ Accept/ })).not.toBeInTheDocument()
  })

  it('prompts to view the source when undecided and the source is not active', () => {
    render(
      <StatementItemView
        {...baseProps}
        item={{
          statement: null,
          createAction: createAction('a1', 'P19', entityContent('Q300'), {
            evidence: [mockEvidence],
          }),
          editActions: [],
        }}
      />,
    )

    expect(screen.getByText('View source to decide')).toBeInTheDocument()
  })

  it('shows decision buttons without evidence', () => {
    render(
      <StatementItemView
        {...baseProps}
        item={{
          statement: null,
          createAction: createAction('a1', 'P19', entityContent('Q300')),
          editActions: [],
        }}
      />,
    )

    expect(screen.getByRole('button', { name: /✓ Accept/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /× Discard/ })).toBeInTheDocument()
  })
})

describe('StatementItemView - edit actions', () => {
  const target = statement('s1', 'P569', timeContent('+1980-01-01T00:00:00Z'))

  function renderItem(actions: Action[], targetStatement = target) {
    return render(
      <StatementItemView
        {...baseProps}
        item={{ statement: targetStatement, createAction: null, editActions: actions }}
      />,
    )
  }

  it('renders a value refinement as old → new', () => {
    renderItem([
      editAction('e1', 's1', [
        { op: 'test', path: '/value', value: timeContent('+1980-01-01T00:00:00Z') },
        { op: 'replace', path: '/value', value: timeContent('+1980-01-02T00:00:00Z') },
      ]),
    ])

    expect(
      screen.getByText(
        (_, element) => element?.textContent === 'January 1, 1980 → January 2, 1980',
      ),
    ).toBeInTheDocument()
  })

  it('renders an entity value refinement using the action entity terms for the new value', () => {
    render(
      <StatementItemView
        {...baseProps}
        item={{
          statement: statement('s1', 'P19', entityContent('Q500')),
          createAction: null,
          editActions: [
            editAction(
              'e1',
              's1',
              [
                { op: 'test', path: '/value', value: entityContent('Q500') },
                { op: 'replace', path: '/value', value: entityContent('Q900') },
              ],
              { entityTerms: terms({ sv: 'Nya staden' }) },
            ),
          ],
        }}
      />,
    )

    expect(
      screen.getByText((_, element) => element?.textContent === 'Q500 → Nya staden'),
    ).toBeInTheDocument()
  })

  it('renders a qualifier refinement as a complete timeframe change', () => {
    const oldQualifier = {
      property: { id: 'P580' },
      value: timeContent('+2018-01-01T00:00:00Z'),
    }
    const newQualifier = {
      property: { id: 'P580' },
      value: timeContent('+2019-01-01T00:00:00Z'),
    }
    renderItem(
      [
        editAction('e1', 's1', [
          { op: 'test', path: '/qualifiers/0', value: oldQualifier },
          { op: 'replace', path: '/qualifiers/0', value: newQualifier },
        ]),
      ],
      statement('s1', 'P39', entityContent('Q400'), { qualifiers: [oldQualifier] }),
    )

    expect(
      screen.getByText(
        (_, element) =>
          element?.textContent === 'January 1, 2018 – present → January 1, 2019 – present',
      ),
    ).toBeInTheDocument()
  })

  it('renders a qualifier append as a complete timeframe change', () => {
    renderItem(
      [
        editAction('e1', 's1', [
          {
            op: 'add',
            path: '/qualifiers/-',
            value: { property: { id: 'P580' }, value: timeContent('+2017-01-01T00:00:00Z') },
          },
        ]),
      ],
      statement('s1', 'P39', entityContent('Q400')),
    )

    expect(
      screen.getByText(
        (_, element) => element?.textContent === 'dates not specified → January 1, 2017 – present',
      ),
    ).toBeInTheDocument()
  })

  it('renders a reference append with its URL', () => {
    renderItem([
      editAction('e1', 's1', [
        {
          op: 'add',
          path: '/references/-',
          value: {
            hash: 'ref-hash',
            parts: [
              { property: { id: 'P854' }, value: entityContent('https://example.com/source') },
            ],
          },
        },
      ]),
    ])

    expect(screen.getByText('+ Reference')).toBeInTheDocument()
    expect(screen.getByText('Reference URL')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'https://example.com/source' })).toBeInTheDocument()
    expect(screen.queryByText(/P854/)).not.toBeInTheDocument()
  })

  it('renders multiple edit actions as separate proposals', () => {
    renderItem(
      [
        editAction('e1', 's1', [
          {
            op: 'add',
            path: '/qualifiers/-',
            value: { property: { id: 'P580' }, value: timeContent('+2017-01-01T00:00:00Z') },
          },
        ]),
        editAction('e2', 's1', [
          {
            op: 'add',
            path: '/qualifiers/-',
            value: { property: { id: 'P582' }, value: timeContent('+2018-01-01T00:00:00Z') },
          },
        ]),
      ],
      statement('s1', 'P39', entityContent('Q400')),
    )

    expect(screen.getByText(/January 1, 2017 – present/)).toBeInTheDocument()
    expect(screen.getByText(/until January 1, 2018/)).toBeInTheDocument()
  })

  it('marks the served decision state on edit action buttons', () => {
    render(
      <StatementItemView
        {...baseProps}
        activeSourceId={mockSource.id}
        decisions={{ e1: false }}
        item={{
          statement: target,
          createAction: null,
          editActions: [
            editAction(
              'e1',
              's1',
              [
                {
                  op: 'add',
                  path: '/qualifiers/-',
                  value: { property: { id: 'P580' }, value: timeContent('+2017-01-01T00:00:00Z') },
                },
              ],
              { evidence: [mockEvidence] },
            ),
          ],
        }}
      />,
    )

    const discard = screen.getByRole('button', { name: /× Discard/ })
    expect(discard).toHaveAttribute('class', expect.stringContaining('bg-danger '))
  })
})
