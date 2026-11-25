import { render, screen, fireEvent } from '@testing-library/react'
import { beforeEach, vi } from 'vitest'
import { mockUseLabelLanguages } from '@/test/mocks'
import { StatementItemView } from './StatementItemView'
import type {
  Action,
  ActionEvidence,
  RestReference,
  RestSnak,
  RestStatement,
  RestValue,
  SourceResponse,
  Statement,
  StatementFact,
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

const cite = (url: string): RestReference => ({
  parts: [{ property: { id: 'P854' }, value: { type: 'value', content: url } }],
})

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

function fact(propertyId: string, value: RestValue, qualifiers: RestSnak[] = []): StatementFact {
  return { property: { id: propertyId }, value, qualifiers }
}

function statement(
  id: string,
  propertyId: string,
  value: RestValue,
  options: {
    documentId?: string
    qualifiers?: RestSnak[]
    references?: RestReference[]
    entityTerms?: TermMaps | null
  } = {},
): Statement {
  return {
    id,
    entity_terms: options.entityTerms ?? null,
    document: {
      id: options.documentId ?? id,
      rank: 'normal',
      property: { id: propertyId },
      value,
      qualifiers: options.qualifiers ?? [],
      references: options.references ?? [],
    },
  }
}

function addAction(
  id: string,
  propertyId: string,
  value: RestValue,
  options: {
    qualifiers?: RestSnak[]
    entityTerms?: TermMaps | null
    evidence?: ActionEvidence[]
    references?: RestReference[]
    groupKey?: string
  } = {},
): Action {
  return {
    id,
    target_wikidata_statement_id: null,
    before: null,
    after: fact(propertyId, value, options.qualifiers ?? []),
    references_to_add: options.references ?? [],
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

function referenceAction(
  id: string,
  statementId: string,
  before: StatementFact,
  references: RestReference[],
  options: { entityTerms?: TermMaps | null; evidence?: ActionEvidence[]; groupKey?: string } = {},
): Action {
  return {
    id,
    target_wikidata_statement_id: statementId,
    before,
    after: before,
    references_to_add: references,
    group_key: options.groupKey ?? id,
    change: 'reference',
    entity_terms: options.entityTerms ?? null,
    evidence: options.evidence ?? [],
  }
}

const baseProps = {
  isNewGroup: false,
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
          proposals: [],
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
          proposals: [],
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
          proposals: [],
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
            references: [cite('https://example.com')],
          }),
          proposals: [],
        }}
      />,
    )

    expect(screen.queryByRole('button', { name: 'Qualifiers' })).not.toBeInTheDocument()
    expect(screen.queryByText(/"P580"/)).not.toBeInTheDocument()
    expect(screen.queryByText(/"P854"/)).not.toBeInTheDocument()
  })
})

describe('StatementItemView - add actions', () => {
  it('renders the proposal with evidence', () => {
    render(
      <StatementItemView
        {...baseProps}
        item={{
          statement: null,
          proposals: [
            [
              addAction('a1', 'P569', timeContent('+1990-05-15T00:00:00Z'), {
                evidence: [mockEvidence],
              }),
            ],
          ],
        }}
      />,
    )

    expect(screen.getByText('May 15, 1990')).toBeInTheDocument()
    expect(screen.getByText('"Test proof line"')).toBeInTheDocument()
  })

  it('shows the source without a separate reference heading for an add', () => {
    render(
      <StatementItemView
        {...baseProps}
        item={{
          statement: null,
          proposals: [
            [
              addAction('a1', 'P19', entityContent('Q300'), {
                entityTerms: terms({ sv: 'Teststad' }),
                evidence: [mockEvidence],
              }),
            ],
          ],
        }}
      />,
    )

    expect(screen.getByText('New statement')).toBeInTheDocument()
    expect(screen.queryByText('Teststad')).not.toBeInTheDocument()
    expect(screen.queryByText('Add reference')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: mockSource.url })).toBeInTheDocument()
    expect(screen.getByText('"Test proof line"')).toBeInTheDocument()
  })

  it('omits a redundant new-statement row when the group title is proposed', () => {
    render(
      <StatementItemView
        {...baseProps}
        isNewGroup
        item={{
          statement: null,
          proposals: [[addAction('a1', 'P19', entityContent('Q300'))]],
        }}
      />,
    )

    expect(screen.queryByText('New statement')).not.toBeInTheDocument()
  })

  it('shows only the proposed timeframe for a new position', () => {
    render(
      <StatementItemView
        {...baseProps}
        item={{
          statement: null,
          proposals: [
            [
              addAction('a1', 'P39', entityContent('Q400'), {
                entityTerms: terms({ sv: 'Statsminister' }),
                qualifiers: [
                  { property: { id: 'P580' }, value: timeContent('+2026-03-15T00:00:00Z') },
                ],
              }),
            ],
          ],
        }}
      />,
    )

    expect(screen.getByText('March 15, 2026 – present')).toBeInTheDocument()
    expect(screen.queryByText('Statsminister')).not.toBeInTheDocument()
  })

  it('shows a proposed term once with both sources and one decision', () => {
    const secondSource = {
      ...mockSource,
      id: 'archived-2',
      url: 'https://de.wikipedia.org/wiki/Test_Politician',
    }
    const qualifiers = [{ property: { id: 'P580' }, value: timeContent('+2026-03-15T00:00:00Z') }]
    render(
      <StatementItemView
        {...baseProps}
        isNewGroup
        activeSourceId={mockSource.id}
        item={{
          statement: null,
          proposals: [
            [
              addAction('a1', 'P39', entityContent('Q400'), {
                qualifiers,
                evidence: [mockEvidence],
                groupKey: 'same-proposal',
              }),
              addAction('a2', 'P39', entityContent('Q400'), {
                qualifiers,
                evidence: [
                  { id: 'ev-2', source: secondSource, supporting_quotes: ['Second proof'] },
                ],
                groupKey: 'same-proposal',
              }),
            ],
          ],
        }}
      />,
    )

    const timeframe = screen.getByText('March 15, 2026 – present')
    expect(timeframe.parentElement).toHaveTextContent('March 15, 2026 – present')
    expect(timeframe.parentElement).not.toHaveTextContent('+')
    expect(timeframe.parentElement).toHaveClass('text-foreground-secondary')
    expect(screen.queryByText('Add reference')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: mockSource.url })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: secondSource.url })).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /✓ Accept/ })).toHaveLength(1)
    expect(screen.getAllByRole('button', { name: /× Discard/ })).toHaveLength(1)
    expect(screen.queryByText('View source to decide')).not.toBeInTheDocument()
  })

  it('combines quotes from the same archived source without repeating the source', () => {
    const onViewSource = vi.fn()
    const first = addAction('a1', 'P19', entityContent('Q300'), {
      entityTerms: terms({ sv: 'Svenska staden', en: 'English City' }),
      evidence: [mockEvidence],
      groupKey: 'g1',
    })
    const second = addAction('a2', 'P19', entityContent('Q300'), {
      evidence: [
        { ...mockEvidence, id: 'ev-2', supporting_quotes: ['Test proof line', 'Second proof'] },
      ],
      groupKey: 'g1',
    })

    render(
      <StatementItemView
        {...baseProps}
        onViewSource={onViewSource}
        item={{ statement: null, proposals: [[first, second]] }}
      />,
    )

    expect(screen.getAllByRole('link', { name: mockSource.url })).toHaveLength(1)
    expect(screen.getAllByText('"Test proof line"')).toHaveLength(1)
    expect(screen.getByText('"Second proof"')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /• View/ }))
    expect(onViewSource).toHaveBeenCalledWith(mockSource, ['Test proof line', 'Second proof'])
  })

  it('shows decided status text when the evidence source is not active', () => {
    render(
      <StatementItemView
        {...baseProps}
        decisions={{ a1: true }}
        item={{
          statement: null,
          proposals: [
            [
              addAction('a1', 'P19', entityContent('Q300'), {
                evidence: [mockEvidence],
              }),
            ],
          ],
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
          proposals: [
            [
              addAction('a1', 'P19', entityContent('Q300'), {
                evidence: [mockEvidence],
              }),
            ],
          ],
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
          proposals: [[addAction('a1', 'P19', entityContent('Q300'))]],
        }}
      />,
    )

    expect(screen.getByRole('button', { name: /✓ Accept/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /× Discard/ })).toBeInTheDocument()
  })
})

describe('StatementItemView - refine and reference actions', () => {
  const target = statement('s1', 'P569', timeContent('+1980-01-01T00:00:00Z'))

  function renderItem(proposals: Action[][], targetStatement = target) {
    return render(
      <StatementItemView {...baseProps} item={{ statement: targetStatement, proposals }} />,
    )
  }

  it('renders a value refinement as old → new', () => {
    renderItem([
      [
        refineAction(
          'e1',
          's1',
          fact('P569', timeContent('+1980-01-01T00:00:00Z')),
          fact('P569', timeContent('+1980-01-02T00:00:00Z')),
        ),
      ],
    ])

    expect(
      screen.getByText(
        (_, element) => element?.textContent === 'January 1, 1980 → January 2, 1980',
      ),
    ).toBeInTheDocument()
  })

  it('renders entity value refinement using action terms for the new value', () => {
    render(
      <StatementItemView
        {...baseProps}
        item={{
          statement: statement('s1', 'P19', entityContent('Q500')),
          proposals: [
            [
              refineAction(
                'e1',
                's1',
                fact('P19', entityContent('Q500')),
                fact('P19', entityContent('Q900')),
                { entityTerms: terms({ sv: 'Nya staden' }) },
              ),
            ],
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
        [
          refineAction(
            'e1',
            's1',
            fact('P39', entityContent('Q400'), [oldQualifier]),
            fact('P39', entityContent('Q400'), [newQualifier]),
          ),
        ],
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
        [
          refineAction(
            'e1',
            's1',
            fact('P39', entityContent('Q400')),
            fact('P39', entityContent('Q400'), [
              { property: { id: 'P580' }, value: timeContent('+2017-01-01T00:00:00Z') },
            ]),
          ),
        ],
      ],
      statement('s1', 'P39', entityContent('Q400')),
    )

    expect(
      screen.getByText(
        (_, element) => element?.textContent === 'dates not specified → January 1, 2017 – present',
      ),
    ).toBeInTheDocument()
  })

  it('marks a reference proposal as an addition', () => {
    renderItem([
      [
        referenceAction('e1', 's1', fact('P569', target.document.value), [cite(mockSource.url)], {
          evidence: [mockEvidence],
        }),
      ],
    ])

    expect(screen.getAllByText('January 1, 1980')).toHaveLength(1)
    const heading = screen.getByRole('heading', { name: 'Add reference' })
    expect(heading).toHaveTextContent('+ Add reference')
    expect(heading).toHaveClass('text-success-foreground')
    expect(screen.getByRole('link', { name: mockSource.url })).toBeInTheDocument()
  })

  it('shows adding multiple references as one change to the existing statement', () => {
    const secondSource = { ...mockSource, id: 'archived-2', url: 'https://example.com/second' }
    const before = fact('P569', target.document.value)
    render(
      <StatementItemView
        {...baseProps}
        activeSourceId={mockSource.id}
        item={{
          statement: target,
          proposals: [
            [
              referenceAction('e1', 's1', before, [cite(mockSource.url)], {
                evidence: [mockEvidence],
                groupKey: 'same-reference',
              }),
              referenceAction('e2', 's1', before, [cite(secondSource.url)], {
                evidence: [{ ...mockEvidence, id: 'ev-2', source: secondSource }],
                groupKey: 'same-reference',
              }),
            ],
          ],
        }}
      />,
    )

    expect(screen.getAllByText('January 1, 1980')).toHaveLength(1)
    expect(screen.queryByText('For: January 1, 1980')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Add references' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: mockSource.url })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: secondSource.url })).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /✓ Accept/ })).toHaveLength(1)
    expect(screen.queryByText('View source to decide')).not.toBeInTheDocument()
  })

  it('renders multiple edit actions as separate proposals', () => {
    renderItem(
      [
        [
          refineAction(
            'e1',
            's1',
            fact('P39', entityContent('Q400')),
            fact('P39', entityContent('Q400'), [
              { property: { id: 'P580' }, value: timeContent('+2017-01-01T00:00:00Z') },
            ]),
          ),
        ],
        [
          refineAction(
            'e2',
            's1',
            fact('P39', entityContent('Q400')),
            fact('P39', entityContent('Q400'), [
              { property: { id: 'P582' }, value: timeContent('+2018-01-01T00:00:00Z') },
            ]),
          ),
        ],
      ],
      statement('s1', 'P39', entityContent('Q400')),
    )

    expect(screen.getByText(/January 1, 2017 – present/)).toBeInTheDocument()
    expect(screen.getByText(/until January 1, 2018/)).toBeInTheDocument()
  })

  it('renders the before/after snapshot when the cached target is missing', () => {
    render(
      <StatementItemView
        {...baseProps}
        item={{
          statement: null,
          proposals: [
            [
              refineAction(
                'e1',
                'Q1$gone',
                fact('P569', timeContent('+1980-01-01T00:00:00Z')),
                fact('P569', timeContent('+1980-01-02T00:00:00Z')),
              ),
            ],
          ],
        }}
      />,
    )

    expect(
      screen.getByText(
        (_, element) => element?.textContent === 'January 1, 1980 → January 2, 1980',
      ),
    ).toBeInTheDocument()
    expect(screen.queryByText('New statement')).not.toBeInTheDocument()
  })

  it('marks the local decision state on edit action buttons', () => {
    render(
      <StatementItemView
        {...baseProps}
        decisions={{ e1: false }}
        activeSourceId={mockSource.id}
        item={{
          statement: target,
          proposals: [
            [
              refineAction(
                'e1',
                's1',
                fact('P569', target.document.value),
                fact('P569', timeContent('+1980-01-02T00:00:00Z')),
                { evidence: [mockEvidence] },
              ),
            ],
          ],
        }}
      />,
    )

    const discard = screen.getByRole('button', { name: /× Discard/ })
    expect(discard).toHaveAttribute('class', expect.stringContaining('bg-danger '))
  })
})
