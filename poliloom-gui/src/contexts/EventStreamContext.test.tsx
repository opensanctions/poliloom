import { describe, it, expect, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useSession } from 'next-auth/react'
import { EventStreamProvider, useEventStream } from './EventStreamContext'
import { mockEventSource } from '@/test-setup'
import type { SSEEvent } from '@/types'

function wrapper({ children }: { children: React.ReactNode }) {
  return <EventStreamProvider>{children}</EventStreamProvider>
}

describe('EventStreamContext', () => {
  it('opens EventSource when authenticated', () => {
    renderHook(() => useEventStream('evaluation_count', vi.fn(), []), { wrapper })

    expect(EventSource).toHaveBeenCalledWith('/api/events')
  })

  it('does not open EventSource when unauthenticated', () => {
    vi.mocked(useSession).mockReturnValue({
      data: null,
      status: 'unauthenticated',
      update: vi.fn(),
    })

    renderHook(() => useEventStream('evaluation_count', vi.fn(), []), { wrapper })

    expect(EventSource).not.toHaveBeenCalled()
  })

  it('dispatches events to matching subscribers', () => {
    const handler = vi.fn()
    renderHook(() => useEventStream('evaluation_count', handler, []), { wrapper })

    const event: SSEEvent = { type: 'evaluation_count', total: 42 }
    act(() => {
      mockEventSource.onmessage?.(new MessageEvent('message', { data: JSON.stringify(event) }))
    })

    expect(handler).toHaveBeenCalledWith(event)
  })

  it('does not dispatch events to non-matching subscribers', () => {
    const handler = vi.fn()
    renderHook(() => useEventStream('evaluation_count', handler, []), { wrapper })

    const event: SSEEvent = {
      type: 'enrichment_complete',
      languages: ['Q1860'],
      countries: ['Q30'],
    }
    act(() => {
      mockEventSource.onmessage?.(new MessageEvent('message', { data: JSON.stringify(event) }))
    })

    expect(handler).not.toHaveBeenCalled()
  })

  it('supports multiple subscribers for same event type', () => {
    const handler1 = vi.fn()
    const handler2 = vi.fn()

    renderHook(
      () => {
        useEventStream('evaluation_count', handler1, [])
        useEventStream('evaluation_count', handler2, [])
      },
      { wrapper },
    )

    const event: SSEEvent = { type: 'evaluation_count', total: 10 }
    act(() => {
      mockEventSource.onmessage?.(new MessageEvent('message', { data: JSON.stringify(event) }))
    })

    expect(handler1).toHaveBeenCalledWith(event)
    expect(handler2).toHaveBeenCalledWith(event)
  })

  it('unsubscribes handler on unmount', () => {
    const handler = vi.fn()
    const { unmount } = renderHook(() => useEventStream('evaluation_count', handler, []), {
      wrapper,
    })

    unmount()

    // Mount a new provider+handler to get a fresh EventSource
    const handler2 = vi.fn()
    const { unmount: unmount2 } = renderHook(
      () => useEventStream('evaluation_count', handler2, []),
      { wrapper },
    )

    const event: SSEEvent = { type: 'evaluation_count', total: 5 }
    act(() => {
      mockEventSource.onmessage?.(new MessageEvent('message', { data: JSON.stringify(event) }))
    })

    expect(handler2).toHaveBeenCalled()
    expect(handler).not.toHaveBeenCalled()

    unmount2()
  })

  it('closes EventSource on unmount', () => {
    const { unmount } = renderHook(() => useEventStream('evaluation_count', vi.fn(), []), {
      wrapper,
    })

    unmount()

    expect(mockEventSource.close).toHaveBeenCalled()
  })

  it('ignores malformed events', () => {
    const handler = vi.fn()
    renderHook(() => useEventStream('evaluation_count', handler, []), { wrapper })

    act(() => {
      mockEventSource.onmessage?.(new MessageEvent('message', { data: 'not json' }))
    })

    expect(handler).not.toHaveBeenCalled()
  })
})
