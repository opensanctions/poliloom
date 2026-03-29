import { describe, it, expect, vi } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { useSession } from 'next-auth/react'
import { EvaluationCountProvider, useEvaluationCount } from './EvaluationCountContext'
import { EventStreamProvider } from './EventStreamContext'
import { mockEventSource } from '@/test/setup'
import type { SSEEvent } from '@/types'

function wrapper({ children }: { children: React.ReactNode }) {
  return (
    <EventStreamProvider>
      <EvaluationCountProvider>{children}</EvaluationCountProvider>
    </EventStreamProvider>
  )
}

describe('EvaluationCountContext', () => {
  it('fetches initial count on mount when authenticated', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ total: 100 }),
    } as Response)

    const { result } = renderHook(() => useEvaluationCount(), { wrapper })

    await waitFor(() => {
      expect(result.current.evaluationCount).toBe(100)
    })

    expect(fetch).toHaveBeenCalledWith('/api/stats/count')
  })

  it('does not fetch when unauthenticated', () => {
    vi.mocked(useSession).mockReturnValue({
      data: null,
      status: 'unauthenticated',
      update: vi.fn(),
    })

    const { result } = renderHook(() => useEvaluationCount(), { wrapper })

    expect(result.current.evaluationCount).toBeNull()
    expect(fetch).not.toHaveBeenCalled()
  })

  it('updates count when evaluation_count event is received', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ total: 50 }),
    } as Response)

    const { result } = renderHook(() => useEvaluationCount(), { wrapper })

    await waitFor(() => {
      expect(result.current.evaluationCount).toBe(50)
    })

    const event: SSEEvent = { type: 'evaluation_count', total: 75 }
    act(() => {
      mockEventSource.onmessage?.(new MessageEvent('message', { data: JSON.stringify(event) }))
    })

    await waitFor(() => {
      expect(result.current.evaluationCount).toBe(75)
    })
  })

  it('handles fetch failure gracefully', async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new Error('Network error'))

    const { result } = renderHook(() => useEvaluationCount(), { wrapper })

    await waitFor(() => {
      expect(fetch).toHaveBeenCalled()
    })
    expect(result.current.evaluationCount).toBeNull()
  })

  it('throws when used outside provider', () => {
    expect(() => {
      renderHook(() => useEvaluationCount())
    }).toThrow('useEvaluationCount must be used within an EvaluationCountProvider')
  })
})
