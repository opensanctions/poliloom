'use client'

import { Header } from '@/components/Header'
import { Hero } from '@/components/Hero'
import { Anchor } from '@/components/Anchor'
import { EvaluationItem } from '@/components/EvaluationItem'
import { PropertyDisplay } from '@/components/PropertyDisplay'
import { Property, PropertyType } from '@/types'

// Sample properties for data types demonstration
const extractedProperty: Property = {
  key: 'demo-extracted',
  id: 'demo-extracted',
  type: PropertyType.P569,
  value: '+1990-05-15T00:00:00Z',
  value_precision: 11,
  proof_line: 'Born on May 15, 1990 in Stockholm, Sweden.',
  archived_page: {
    id: 'demo-archive-1',
    url: 'https://example.gov/politicians/bio',
    content_hash: 'abc123',
    fetch_timestamp: '2024-01-15T10:00:00Z',
  },
}

const wikidataExistingProperty: Property = {
  key: 'demo-wikidata-existing',
  id: 'demo-wikidata-existing',
  type: PropertyType.P569,
  value: '+1990-05-14T00:00:00Z',
  value_precision: 11,
  proof_line: 'Date of birth: May 14, 1990.',
  statement_id: 'Q12345$XYZ-789',
  references: [
    {
      hash: 'xyz789abc123',
      snaks: {
        P854: [
          {
            datatype: 'url',
            property: 'P854',
            snaktype: 'value',
            datavalue: {
              type: 'string',
              value: 'https://example.gov/old-bio',
            },
          },
        ],
      },
      'snaks-order': ['P854'],
    },
  ],
}

// Sample properties for three-state demonstration
const samplePropertySkip: Property = {
  key: 'demo-property-skip',
  id: 'demo-property-skip',
  type: PropertyType.P569,
  value: '+1990-05-15T00:00:00Z',
  value_precision: 11,
  proof_line: 'Born on May 15, 1990 in Stockholm, Sweden.',
  archived_page: {
    id: 'demo-archive-2',
    url: 'https://example.gov/politicians/profile',
    content_hash: 'def456',
    fetch_timestamp: '2024-01-20T14:30:00Z',
  },
}

const samplePropertyAccept: Property = {
  key: 'demo-property-accept',
  id: 'demo-property-accept',
  type: PropertyType.P569,
  value: '+1985-03-22T00:00:00Z',
  value_precision: 11,
  proof_line: 'Date of birth: March 22, 1985.',
  archived_page: {
    id: 'demo-archive-3',
    url: 'https://parliament.example.com/members/details',
    content_hash: 'ghi789',
    fetch_timestamp: '2024-02-01T09:15:00Z',
  },
}

const samplePropertyDiscard: Property = {
  key: 'demo-property-discard',
  id: 'demo-property-discard',
  type: PropertyType.P569,
  value: '+1992-01-01T00:00:00Z',
  value_precision: 9,
  proof_line: 'Born in 1992.',
  archived_page: {
    id: 'demo-archive-4',
    url: 'https://en.wikipedia.org/wiki/Example_Politician',
    content_hash: 'jkl012',
    fetch_timestamp: '2024-02-10T16:45:00Z',
  },
}

// Sample property that's already in Wikidata (for discard demo)
const wikidataProperty: Property = {
  key: 'demo-wikidata-property',
  id: 'demo-wikidata-property',
  type: PropertyType.P39,
  entity_id: 'Q486839',
  entity_name: 'Member of Parliament',
  proof_line: 'Served as MP from 2015 to 2019.',
  statement_id: 'Q12345$ABC-123',
  qualifiers: {
    P580: [
      {
        datavalue: {
          value: {
            time: '+2015-01-01T00:00:00Z',
            precision: 11,
          },
        },
      },
    ],
    P582: [
      {
        datavalue: {
          value: {
            time: '+2019-12-31T00:00:00Z',
            precision: 11,
          },
        },
      },
    ],
  },
  references: [
    {
      hash: 'abc123def456',
      snaks: {
        P854: [
          {
            datatype: 'url',
            property: 'P854',
            snaktype: 'value',
            datavalue: {
              type: 'string',
              value: 'https://example.gov/bio',
            },
          },
        ],
      },
      'snaks-order': ['P854'],
    },
  ],
}

export default function GuidePage() {
  // All evaluation maps locked to their demo states
  const skipEvaluations = new Map<string, boolean>()
  const acceptEvaluations = new Map<string, boolean>([['demo-property-accept', true]])
  const discardEvaluations = new Map<string, boolean>([['demo-property-discard', false]])
  const wikidataEvaluations = new Map<string, boolean>([['demo-wikidata-property', false]])

  return (
    <>
      <Header />
      <main className="bg-gray-50 min-h-0 overflow-y-auto">
        <Hero
          title="How It Works"
          description="Learn how to review and evaluate politician data for Wikidata. This guide will walk you through the process of confirming birth dates, positions, and other details extracted from government sources."
        />

        <div className="max-w-6xl mx-auto px-8 py-12">
          <div className="space-y-8">
            {/* Introduction */}
            <div>
              <h2 className="text-2xl font-bold text-gray-900 mb-2">Your Role</h2>
              <div className="prose max-w-none space-y-3">
                <p className="text-gray-600 leading-relaxed">
                  PoliLoom extracts statements on politicians from government portals and Wikipedia.
                  Your job is simple:{' '}
                  <strong className="text-gray-900">review these proposed edits</strong> and decide
                  whether they&apos;re accurate enough to add to Wikidata. You&apos;ll see extracted
                  statements like birth dates, positions, and birthplaces that need your
                  confirmation before being added.
                </p>

                <p className="text-gray-600 leading-relaxed">
                  Each statement includes a{' '}
                  <strong className="text-gray-900">&quot;view archive&quot; button</strong> that
                  shows you the original source page with the relevant text highlighted. Use this to
                  verify the information before confirming or discarding.
                </p>
              </div>
            </div>

            {/* Understanding the Data */}
            <div>
              <h2 className="text-2xl font-bold text-gray-900 mb-2">Understanding the Data</h2>
              <p className="text-gray-600 mb-6">
                As you review politicians, you&apos;ll encounter two types of information:
              </p>

              <div className="space-y-8">
                {/* Extracted Information example */}
                <div>
                  <EvaluationItem title="Birth Date" hasNewData={true}>
                    <PropertyDisplay property={extractedProperty} evaluations={skipEvaluations} />
                  </EvaluationItem>
                  <div className="mt-3 prose max-w-none">
                    <p className="text-gray-600 leading-relaxed">
                      <strong className="text-gray-900">Extracted Information:</strong> New proposed
                      statements <strong className="text-gray-900">not yet in Wikidata</strong>.
                      These items are waiting for your review before they can be submitted.
                    </p>
                  </div>
                </div>

                {/* Current in Wikidata example */}
                <div>
                  <EvaluationItem title="Birth Date" hasNewData={false}>
                    <PropertyDisplay
                      property={wikidataExistingProperty}
                      evaluations={skipEvaluations}
                    />
                  </EvaluationItem>
                  <div className="mt-3 prose max-w-none">
                    <p className="text-gray-600 leading-relaxed">
                      <strong className="text-gray-900">Current in Wikidata:</strong> Data that{' '}
                      <strong className="text-gray-900">already exists in Wikidata</strong>.
                      You&apos;ll see the existing statement with its metadata (references and
                      qualifiers).
                    </p>
                  </div>
                </div>
              </div>

              {/* Summary paragraph */}
              <div className="mt-6 prose max-w-none">
                <p className="text-gray-600 leading-relaxed">
                  This distinction is important because{' '}
                  <strong className="text-gray-900">
                    accepting extracted data adds something new, while discarding Wikidata data
                    removes something that&apos;s already there
                  </strong>
                  .
                </p>
              </div>
            </div>

            {/* Interactive Demo */}
            <div>
              <h2 className="text-2xl font-bold text-gray-900 mb-2">
                Evaluation Actions Explained
              </h2>
              <p className="text-gray-600 mb-6">
                For each proposed property statement, you have three options:
              </p>

              <div className="space-y-8">
                {/* Accept example */}
                <div>
                  <EvaluationItem title="Birth Date" hasNewData={true}>
                    <PropertyDisplay
                      property={samplePropertyAccept}
                      evaluations={acceptEvaluations}
                    />
                  </EvaluationItem>
                  <div className="mt-3 prose max-w-none">
                    <p className="text-gray-600 leading-relaxed">
                      <strong className="text-gray-900">Accept:</strong> Confirm this data is
                      accurate. Accepted items will be submitted to Wikidata with proper references.
                    </p>
                  </div>
                </div>

                {/* Discard example */}
                <div>
                  <EvaluationItem title="Birth Date" hasNewData={true}>
                    <PropertyDisplay
                      property={samplePropertyDiscard}
                      evaluations={discardEvaluations}
                    />
                  </EvaluationItem>
                  <div className="mt-3 prose max-w-none">
                    <p className="text-gray-600 leading-relaxed">
                      <strong className="text-gray-900">Discard:</strong> Mark this data as
                      incorrect or unreliable. Discarded items will not be added to Wikidata.
                    </p>
                  </div>
                </div>

                {/* Skip example */}
                <div>
                  <EvaluationItem title="Birth Date" hasNewData={true}>
                    <PropertyDisplay property={samplePropertySkip} evaluations={skipEvaluations} />
                  </EvaluationItem>
                  <div className="mt-3 prose max-w-none">
                    <p className="text-gray-600 leading-relaxed">
                      <strong className="text-gray-900">Skip:</strong> Leave this item unreviewed.
                      It will remain in the queue for later evaluation by you or another reviewer.
                    </p>
                  </div>
                </div>
              </div>

              {/* Comfort paragraph after demo */}
              <div className="mt-6 prose max-w-none">
                <p className="text-gray-600 leading-relaxed">
                  <strong className="text-gray-900">Not sure?</strong> That&apos;s completely fine:{' '}
                  <strong className="text-gray-900">just skip it!</strong> You&apos;re never
                  required to make a decision on any item. If something feels uncertain, leave it
                  for another reviewer or take a moment to check the politician&apos;s Wikidata page
                  yourself. Every contribution helps, even if you only evaluate the items
                  you&apos;re confident about.
                </p>
              </div>
            </div>

            {/* Replacing existing Wikidata statements */}
            <div>
              <h2 className="text-2xl font-bold text-gray-900 mb-2">
                Replacing Existing Statements
              </h2>
              <p className="text-gray-600 mb-6">
                Sometimes you might want to replace existing Wikidata data with more accurate
                information. To do this,{' '}
                <strong className="text-gray-900">
                  you can discard the old statement and accept the new one
                </strong>
                . However,{' '}
                <strong className="text-gray-900">
                  make sure to keep metadata that won&apos;t be replaced.
                </strong>
              </p>
              <EvaluationItem title={wikidataProperty.entity_name} hasNewData={false}>
                <PropertyDisplay
                  property={wikidataProperty}
                  evaluations={wikidataEvaluations}
                  shouldAutoOpen={false}
                />
              </EvaluationItem>

              {/* Explanation paragraph */}
              <div className="mt-4 prose max-w-none">
                <p className="text-gray-600 leading-relaxed">
                  If there&apos;s no metadata attached, it&apos;s perfectly fine to discard and
                  replace with more correct data. However, if the existing statement has metadata,
                  consider editing it directly on Wikidata instead , as PoliLoom currently
                  doesn&apos;t support editing metadata.{' '}
                  <strong className="text-gray-900">When in doubt, skip it</strong> and let someone
                  else take a closer look.
                </p>
              </div>
            </div>

            {/* Final confidence boost */}
            <div>
              <h2 className="text-2xl font-bold text-gray-900 mb-2">You&apos;re Ready!</h2>
              <div className="prose max-w-none">
                <p className="text-gray-600 leading-relaxed">
                  That&apos;s all there is to it! Review what you&apos;re confident about, skip what
                  you&apos;re not, and check Wikidata whenever you need more context. You&apos;ve
                  got this:{' '}
                  <strong className="text-gray-900">
                    every evaluation you make helps improve the quality of data available to
                    everyone
                  </strong>
                  .
                </p>
              </div>
            </div>

            {/* CTA */}
            <div className="mt-12 flex justify-end">
              <Anchor
                href="/"
                className="bg-indigo-600 text-white font-semibold hover:bg-indigo-700 px-8 py-4 rounded-lg transition-colors shadow-sm hover:shadow-md"
              >
                Let&apos;s Get Started
              </Anchor>
            </div>
          </div>
        </div>
      </main>
    </>
  )
}
