'use client'

import { useState, useEffect, useRef } from 'react'
import { Header } from '@/components/Header'
import { Anchor } from '@/components/Anchor'
import { EvaluationItem } from '@/components/EvaluationItem'
import { PropertyDisplay } from '@/components/PropertyDisplay'
import { Property, PropertyType } from '@/types'

// Sample property for demonstration
const sampleProperty: Property = {
  key: 'demo-property',
  id: 'demo-property',
  type: PropertyType.P569,
  value: '+1990-05-15T00:00:00Z',
  value_precision: 11,
  proof_line: 'Born on May 15, 1990 in Stockholm, Sweden.',
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

type DemoState = 'none' | 'accept' | 'discard'

const stateExplanations: Record<DemoState, { title: string; description: string }> = {
  none: {
    title: 'Skip',
    description: 'Leave this item unreviewed. It will remain in the queue for later evaluation.',
  },
  accept: {
    title: 'Accept',
    description:
      'Confirm this data is accurate. Accepted items will be submitted to Wikidata with proper references.',
  },
  discard: {
    title: 'Discard',
    description:
      'Mark this data as incorrect or unreliable. Discarded items will not be added to Wikidata.',
  },
}

export default function GuidePage() {
  const [currentState, setCurrentState] = useState<DemoState>('none')
  const [evaluations, setEvaluations] = useState<Map<string, boolean>>(new Map())
  const [wikidataEvaluations, setWikidataEvaluations] = useState<Map<string, boolean>>(
    new Map([['demo-wikidata-property', false]]),
  )
  const timeoutRef = useRef<NodeJS.Timeout | null>(null)
  const stateIndexRef = useRef(0)

  const scheduleNextCycle = (delay: number) => {
    const states: DemoState[] = ['accept', 'discard', 'none']

    timeoutRef.current = setTimeout(() => {
      stateIndexRef.current = (stateIndexRef.current + 1) % states.length
      const newState = states[stateIndexRef.current]
      setCurrentState(newState)

      // Update evaluations map based on state
      const newEvaluations = new Map<string, boolean>()
      if (newState === 'accept') {
        newEvaluations.set('demo-property', true)
      } else if (newState === 'discard') {
        newEvaluations.set('demo-property', false)
      }
      setEvaluations(newEvaluations)

      // Schedule next cycle with default 2 second delay
      scheduleNextCycle(2000)
    }, delay)
  }

  // Start cycling on mount
  useEffect(() => {
    scheduleNextCycle(2000)

    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }
    }
  }, [])

  const handleAction = (propertyId: string, action: 'confirm' | 'discard') => {
    // Clear current timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = null
    }

    setEvaluations((prev) => {
      const newMap = new Map(prev)
      const currentValue = newMap.get(propertyId)
      const targetValue = action === 'confirm'

      if (currentValue === targetValue) {
        // Toggle off - remove from map
        newMap.delete(propertyId)
        setCurrentState('none')
      } else {
        // Set new value
        newMap.set(propertyId, targetValue)
        setCurrentState(targetValue ? 'accept' : 'discard')
      }
      return newMap
    })

    // Resume cycling after 4 seconds
    scheduleNextCycle(4000)
  }

  const handleShowArchived = () => {
    // No-op for demo
  }

  const handleHover = () => {
    // No-op for demo
  }

  const handleWikidataAction = (propertyId: string, action: 'confirm' | 'discard') => {
    setWikidataEvaluations((prev) => {
      const newMap = new Map(prev)
      const currentValue = newMap.get(propertyId)
      const targetValue = action === 'confirm'

      if (currentValue === targetValue) {
        // Toggle off - remove from map
        newMap.delete(propertyId)
      } else {
        // Set new value
        newMap.set(propertyId, targetValue)
      }
      return newMap
    })
  }

  return (
    <>
      <Header />
      <main className="bg-gray-50 py-12 px-4 sm:px-6 lg:px-8 min-h-0 overflow-y-auto">
        <div className="max-w-4xl mx-auto">
          <div className="bg-white shadow rounded-lg">
            <div className="px-6 py-4 border-b border-gray-200">
              <h1 className="text-xl font-semibold text-gray-900">How It Works</h1>
              <p className="mt-1 text-sm text-gray-600">
                Learn how to review and evaluate politician data for Wikidata.
              </p>
            </div>

            <div className="px-6 py-6 space-y-8">
              {/* Introduction */}
              <div className="prose max-w-none space-y-3">
                <p className="text-sm text-gray-600 leading-relaxed">
                  PoliLoom extracts politician data from government portals and Wikipedia. Your job
                  is simple: <strong>review new data</strong> and decide whether it&apos;s accurate
                  enough to add to Wikidata. You&apos;ll see extracted information like birth dates,
                  positions, and birthplaces that need your confirmation before being added.
                </p>
                <p className="text-sm text-gray-600 leading-relaxed">
                  Sometimes you&apos;ll notice that{' '}
                  <strong>existing data on Wikidata conflicts with the new data</strong>. If the new
                  data is better sourced or more accurate, you have the option to discard the
                  existing statement. This removes it from Wikidata along with its metadata,
                  allowing the improved version to be added instead.
                </p>
              </div>

              {/* Interactive Demo */}
              <div>
                <h2 className="text-lg font-medium text-gray-900 mb-4">Try It: Three Actions</h2>

                <EvaluationItem title="Birth Date">
                  <PropertyDisplay
                    property={sampleProperty}
                    evaluations={evaluations}
                    onAction={handleAction}
                    onShowArchived={handleShowArchived}
                    onHover={handleHover}
                    activeArchivedPageId={null}
                  />
                </EvaluationItem>

                {/* State Explanation */}
                <div
                  className={`mt-4 p-4 rounded-lg ${
                    currentState === 'accept'
                      ? 'bg-green-50 border border-green-200'
                      : currentState === 'discard'
                        ? 'bg-red-50 border border-red-200'
                        : 'bg-blue-50 border border-blue-200'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div
                      className={`flex-shrink-0 w-2 h-2 rounded-full mt-2 ${
                        currentState === 'accept'
                          ? 'bg-green-500'
                          : currentState === 'discard'
                            ? 'bg-red-500'
                            : 'bg-blue-500'
                      }`}
                    />
                    <div>
                      <h3
                        className={`font-semibold ${
                          currentState === 'accept'
                            ? 'text-green-900'
                            : currentState === 'discard'
                              ? 'text-red-900'
                              : 'text-blue-900'
                        }`}
                      >
                        {stateExplanations[currentState].title}
                      </h3>
                      <p
                        className={`text-sm mt-1 ${
                          currentState === 'accept'
                            ? 'text-green-800'
                            : currentState === 'discard'
                              ? 'text-red-800'
                              : 'text-blue-800'
                        }`}
                      >
                        {stateExplanations[currentState].description}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Comfort paragraph after demo */}
                <div className="mt-4 prose max-w-none">
                  <p className="text-sm text-gray-600 leading-relaxed">
                    <strong>Not sure?</strong> That&apos;s completely fine:{' '}
                    <strong>just skip it!</strong> You&apos;re never required to make a decision on
                    any item. If something feels uncertain, leave it for another reviewer or take a
                    moment to check the politician&apos;s Wikidata page yourself. Every contribution
                    helps, even if you only evaluate the items you&apos;re confident about.
                  </p>
                </div>
              </div>

              {/* Discarding existing Wikidata items */}
              <div>
                <h2 className="text-lg font-medium text-gray-900 mb-4">Discarding Existing Data</h2>
                <EvaluationItem title={wikidataProperty.entity_name}>
                  <PropertyDisplay
                    property={wikidataProperty}
                    evaluations={wikidataEvaluations}
                    onAction={handleWikidataAction}
                    onShowArchived={handleShowArchived}
                    onHover={handleHover}
                    activeArchivedPageId={null}
                    shouldAutoOpen={false}
                  />
                </EvaluationItem>

                {/* Metadata info box */}
                <div
                  className={`mt-4 p-4 rounded-lg ${
                    wikidataEvaluations.get('demo-wikidata-property') === false
                      ? 'bg-red-50 border border-red-200'
                      : 'bg-blue-50 border border-blue-200'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div
                      className={`flex-shrink-0 w-2 h-2 rounded-full mt-2 ${
                        wikidataEvaluations.get('demo-wikidata-property') === false
                          ? 'bg-red-500'
                          : 'bg-blue-500'
                      }`}
                    />
                    <div>
                      {wikidataEvaluations.get('demo-wikidata-property') === false ? (
                        <>
                          <h3 className="font-semibold text-red-900">
                            Statement Marked for Deletion
                          </h3>
                          <p className="text-sm mt-1 text-red-800">
                            This statement and its metadata will be removed from Wikidata if you
                            proceed.
                          </p>
                        </>
                      ) : (
                        <>
                          <h3 className="font-semibold text-blue-900">
                            Existing Wikidata Statement
                          </h3>
                          <p className="text-sm mt-1 text-blue-800">
                            This statement is currently on Wikidata with metadata attached.
                          </p>
                        </>
                      )}
                    </div>
                  </div>
                </div>

                {/* Comfort paragraph after discard demo */}
                <div className="mt-4 prose max-w-none">
                  <p className="text-sm text-gray-600 leading-relaxed">
                    When discarding existing Wikidata statements,{' '}
                    <strong>pay attention to the metadata that&apos;s attached</strong>: dates,
                    references, and qualifiers. These discards often replace one version with
                    another, so{' '}
                    <strong>compare what&apos;s being removed with what will be inserted</strong>.
                    If the existing metadata looks valuable or you&apos;re unsure about the
                    replacement, skip it and let someone else take a closer look.
                  </p>
                </div>
              </div>

              {/* Final confidence boost */}
              <div>
                <h2 className="text-lg font-medium text-gray-900 mb-4">You&apos;re Ready!</h2>
                <div className="prose max-w-none">
                  <p className="text-sm text-gray-600 leading-relaxed">
                    That&apos;s all there is to it! Review what you&apos;re confident about, skip
                    what you&apos;re not, and check Wikidata whenever you need more context.
                    You&apos;ve got this:{' '}
                    <strong>
                      every evaluation you make helps improve the quality of data available to
                      everyone
                    </strong>
                    .
                  </p>
                </div>
              </div>
            </div>

            <div className="px-6 py-4 border-t border-gray-200 flex justify-end">
              <Anchor
                href="/"
                className="bg-indigo-600 text-white font-medium hover:bg-indigo-700 px-4 py-2 rounded-md transition-colors"
              >
                Start Evaluating
              </Anchor>
            </div>
          </div>
        </div>
      </main>
    </>
  )
}
