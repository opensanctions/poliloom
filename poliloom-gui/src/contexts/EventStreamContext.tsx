'use client'

import { createContext, useEffect, useRef, useCallback, useState, useContext } from 'react'
import { useSession } from 'next-auth/react'
import type { SSEEvent, SSEEventType, SSEEventByType } from '@/types'

type EventHandler = (event: SSEEvent) => void

interface EventStreamContextType {
  subscribe: (eventType: SSEEventType, handler: EventHandler) => () => void
}

const EventStreamContext = createContext<EventStreamContextType | null>(null)

export function EventStreamProvider({ children }: { children: React.ReactNode }) {
  const { status } = useSession()
  const listenersRef = useRef<Map<string, Set<EventHandler>>>(new Map())
  const eventSourceRef = useRef<EventSource | null>(null)
  const [, setConnected] = useState(false)

  useEffect(() => {
    if (status !== 'authenticated') return

    const es = new EventSource('/api/events')
    eventSourceRef.current = es

    es.onmessage = (e) => {
      try {
        const event: SSEEvent = JSON.parse(e.data)
        const handlers = listenersRef.current.get(event.type)
        if (handlers) {
          handlers.forEach((handler) => handler(event))
        }
      } catch {
        // ignore malformed events
      }
    }

    es.onopen = () => setConnected(true)
    es.onerror = () => setConnected(false)

    return () => {
      es.close()
      eventSourceRef.current = null
      setConnected(false)
    }
  }, [status])

  const subscribe = useCallback((eventType: SSEEventType, handler: EventHandler) => {
    if (!listenersRef.current.has(eventType)) {
      listenersRef.current.set(eventType, new Set())
    }
    listenersRef.current.get(eventType)!.add(handler)

    return () => {
      const handlers = listenersRef.current.get(eventType)
      if (handlers) {
        handlers.delete(handler)
        if (handlers.size === 0) {
          listenersRef.current.delete(eventType)
        }
      }
    }
  }, [])

  return <EventStreamContext.Provider value={{ subscribe }}>{children}</EventStreamContext.Provider>
}

export function useEventStream<T extends SSEEventType>(
  eventType: T,
  handler: (event: SSEEventByType<T>) => void,
  deps: React.DependencyList,
) {
  const context = useContext(EventStreamContext)
  const handlerRef = useRef(handler)
  handlerRef.current = handler

  useEffect(() => {
    if (!context) return
    const stableHandler: EventHandler = (event) => handlerRef.current(event as SSEEventByType<T>)
    return context.subscribe(eventType, stableHandler)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [context, eventType, ...deps])
}
