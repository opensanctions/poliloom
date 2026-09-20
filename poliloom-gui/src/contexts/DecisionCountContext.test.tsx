import { describe, it, expect } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { DecisionCountProvider, useDecisionCount } from './DecisionCountContext'
import { EventStreamProvider } from './EventStreamContext'
import { mockEventSource } from '@/test/setup'
import type { SSEEvent } from '@/types'

describe('DecisionCountContext', () => {
  it('exposes the seeded initial count', () => {
    const { result } = renderHook(() => useDecisionCount(), {
      wrapper: ({ children }) => (
        <EventStreamProvider>
          <DecisionCountProvider initialCount={100}>{children}</DecisionCountProvider>
        </EventStreamProvider>
      ),
    })
    expect(result.current.decisionCount).toBe(100)
  })

  it('exposes null when seeded with null', () => {
    const { result } = renderHook(() => useDecisionCount(), {
      wrapper: ({ children }) => (
        <EventStreamProvider>
          <DecisionCountProvider initialCount={null}>{children}</DecisionCountProvider>
        </EventStreamProvider>
      ),
    })
    expect(result.current.decisionCount).toBeNull()
  })

  it('updates count when decision_count event is received', async () => {
    const { result } = renderHook(() => useDecisionCount(), {
      wrapper: ({ children }) => (
        <EventStreamProvider>
          <DecisionCountProvider initialCount={50}>{children}</DecisionCountProvider>
        </EventStreamProvider>
      ),
    })

    const event: SSEEvent = { type: 'decision_count', total: 75 }
    act(() => {
      mockEventSource.onmessage?.(new MessageEvent('message', { data: JSON.stringify(event) }))
    })

    await waitFor(() => {
      expect(result.current.decisionCount).toBe(75)
    })
  })

  it('throws when used outside provider', () => {
    expect(() => {
      renderHook(() => useDecisionCount())
    }).toThrow('useDecisionCount must be used within a DecisionCountProvider')
  })
})
