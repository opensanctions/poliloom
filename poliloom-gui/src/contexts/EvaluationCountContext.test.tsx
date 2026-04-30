import { describe, it, expect } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { EvaluationCountProvider, useEvaluationCount } from './EvaluationCountContext'
import { EventStreamProvider } from './EventStreamContext'
import { mockEventSource } from '@/test/setup'
import type { SSEEvent } from '@/types'

describe('EvaluationCountContext', () => {
  it('exposes the seeded initial count', () => {
    const { result } = renderHook(() => useEvaluationCount(), {
      wrapper: ({ children }) => (
        <EventStreamProvider>
          <EvaluationCountProvider initialCount={100}>{children}</EvaluationCountProvider>
        </EventStreamProvider>
      ),
    })
    expect(result.current.evaluationCount).toBe(100)
  })

  it('exposes null when seeded with null', () => {
    const { result } = renderHook(() => useEvaluationCount(), {
      wrapper: ({ children }) => (
        <EventStreamProvider>
          <EvaluationCountProvider initialCount={null}>{children}</EvaluationCountProvider>
        </EventStreamProvider>
      ),
    })
    expect(result.current.evaluationCount).toBeNull()
  })

  it('updates count when evaluation_count event is received', async () => {
    const { result } = renderHook(() => useEvaluationCount(), {
      wrapper: ({ children }) => (
        <EventStreamProvider>
          <EvaluationCountProvider initialCount={50}>{children}</EvaluationCountProvider>
        </EventStreamProvider>
      ),
    })

    const event: SSEEvent = { type: 'evaluation_count', total: 75 }
    act(() => {
      mockEventSource.onmessage?.(new MessageEvent('message', { data: JSON.stringify(event) }))
    })

    await waitFor(() => {
      expect(result.current.evaluationCount).toBe(75)
    })
  })

  it('throws when used outside provider', () => {
    expect(() => {
      renderHook(() => useEvaluationCount())
    }).toThrow('useEvaluationCount must be used within an EvaluationCountProvider')
  })
})
