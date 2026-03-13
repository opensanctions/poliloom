'use client'

import { createContext, useEffect, useRef, useCallback, useState } from 'react'
import { useSession } from 'next-auth/react'

type EventHandler = (event: { archived_page_id: string; status: string; error?: string }) => void

interface EventStreamContextType {
  subscribe: (archivedPageId: string, handler: EventHandler) => () => void
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
        const event = JSON.parse(e.data)
        const handlers = listenersRef.current.get(event.archived_page_id)
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

  const subscribe = useCallback((archivedPageId: string, handler: EventHandler) => {
    if (!listenersRef.current.has(archivedPageId)) {
      listenersRef.current.set(archivedPageId, new Set())
    }
    listenersRef.current.get(archivedPageId)!.add(handler)

    return () => {
      const handlers = listenersRef.current.get(archivedPageId)
      if (handlers) {
        handlers.delete(handler)
        if (handlers.size === 0) {
          listenersRef.current.delete(archivedPageId)
        }
      }
    }
  }, [])

  return <EventStreamContext.Provider value={{ subscribe }}>{children}</EventStreamContext.Provider>
}
