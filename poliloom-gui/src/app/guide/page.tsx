'use client'

import { useState, useEffect, useRef } from 'react'
import { Header } from '@/components/Header'
import { EvaluationItem } from '@/components/EvaluationItem'
import { PropertyDisplay } from '@/components/PropertyDisplay'
import { Property, PropertyType } from '@/types'

// Sample property for demonstration
const sampleProperty: Property = {
  id: 'demo-property',
  type: PropertyType.P569,
  value: '+1990-05-15T00:00:00Z',
  value_precision: 11,
  proof_line: 'Born on May 15, 1990 in Stockholm, Sweden.',
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

  return (
    <>
      <Header />
      <main className="bg-gray-50 py-12 px-4 sm:px-6 lg:px-8 min-h-0 overflow-y-auto">
        <div className="max-w-4xl mx-auto">
          <div className="bg-white shadow rounded-lg">
            <div className="px-6 py-4 border-b border-gray-200">
              <h1 className="text-xl font-semibold text-gray-900">How It Works</h1>
            </div>

            <div className="px-6 py-6 space-y-8">
              {/* Introduction */}
              <div className="prose max-w-none">
                <p className="text-lg text-gray-700 leading-relaxed">
                  PoliLoom extracts politician data from government portals and Wikipedia. Your job
                  is simple: review each piece of information and decide whether it&apos;s accurate
                  enough to add to Wikidata.
                </p>
              </div>

              {/* Interactive Demo */}
              <div>
                <h2 className="text-lg font-semibold text-gray-900 mb-4">Try It: Three Actions</h2>
                <EvaluationItem title={<span className="font-bold">Birth Date</span>}>
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
              </div>
            </div>
          </div>
        </div>
      </main>
    </>
  )
}
