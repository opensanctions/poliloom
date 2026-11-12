import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ReferenceView } from './ReferenceView'
import type { RestSnak, RestStatement } from '@/types'

function snak(propertyId: string, dataType: string, content: unknown): RestSnak {
  return {
    property: { id: propertyId, data_type: dataType },
    value: { type: 'value', content },
  }
}

function reference(parts: RestSnak[]): RestStatement['references'][number] {
  return { parts }
}

describe('ReferenceView', () => {
  it('renders known citation fields and links URL and entity values', () => {
    render(
      <ReferenceView
        reference={reference([
          snak('P4656', 'url', 'https://en.wikipedia.org/w/index.php?title=Example'),
          snak('P143', 'wikibase-item', 'Q328'),
        ])}
        proposed
      />,
    )

    expect(screen.getByText('+ Reference')).toBeInTheDocument()
    expect(screen.getByText('Wikimedia import URL')).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: 'https://en.wikipedia.org/w/index.php?title=Example' }),
    ).toHaveAttribute('href', 'https://en.wikipedia.org/w/index.php?title=Example')
    expect(screen.getByRole('link', { name: 'Q328' })).toHaveAttribute(
      'href',
      'https://www.wikidata.org/wiki/Q328',
    )
  })

  it('formats arbitrary reference values by datatype', () => {
    render(
      <ReferenceView
        reference={reference([
          snak('P813', 'time', {
            time: '+2015-07-07T00:00:00Z',
            precision: 11,
            calendarmodel: 'http://www.wikidata.org/entity/Q1985727',
          }),
          snak('P1476', 'monolingualtext', { text: 'Example title', language: 'en' }),
          snak('P1104', 'quantity', { amount: '+42', unit: '1' }),
          snak('P625', 'globe-coordinate', {
            latitude: 52.5,
            longitude: 13.4,
            precision: 0.01,
            globe: 'http://www.wikidata.org/entity/Q2',
          }),
        ])}
      />,
    )

    expect(screen.getByText('July 7, 2015')).toBeInTheDocument()
    expect(screen.getByText(/Example title/)).toBeInTheDocument()
    expect(screen.getByText('42')).toBeInTheDocument()
    expect(screen.getByText('52.5, 13.4')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'P1476' })).toHaveAttribute(
      'href',
      'https://www.wikidata.org/wiki/Property:P1476',
    )
  })

  it('keeps empty and unusual references visible', () => {
    const { rerender } = render(<ReferenceView reference={reference([])} />)
    expect(screen.getByText('No reference details')).toBeInTheDocument()

    rerender(
      <ReferenceView
        reference={{
          parts: [
            { property: { id: 'P1', data_type: 'string' }, value: { type: 'somevalue' } },
            { property: { id: 'P2', data_type: 'string' }, value: { type: 'novalue' } },
            snak('P3', 'future-type', { arbitrary: ['value'] }),
          ],
        }}
      />,
    )

    expect(screen.getByText('unknown')).toBeInTheDocument()
    expect(screen.getByText('no value')).toBeInTheDocument()
    expect(screen.getByText('{"arbitrary":["value"]}')).toBeInTheDocument()
  })
})
