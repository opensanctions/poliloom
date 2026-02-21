'use client'

import React, { createContext, useContext, useSyncExternalStore, useCallback } from 'react'

const SESSION_KEY = 'evaluationSession'
const SESSION_GOAL = 5

interface SessionState {
  active: boolean
  count: number
}

interface EvaluationSessionContextType {
  isSessionActive: boolean
  completedCount: number
  sessionGoal: number

  startSession: () => void
  submitAndAdvance: () => { sessionComplete: boolean }
  endSession: () => void
}

export const EvaluationSessionContext = createContext<EvaluationSessionContextType | undefined>(
  undefined,
)

// --- Store: sessionStorage is the single source of truth ---

const listeners = new Set<() => void>()

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

function notify() {
  listeners.forEach((l) => l())
}

function getSnapshot(): string {
  return sessionStorage.getItem(SESSION_KEY) ?? ''
}

function getServerSnapshot(): string {
  return ''
}

function parse(raw: string): SessionState {
  if (!raw) return { active: false, count: 0 }
  try {
    return JSON.parse(raw)
  } catch {
    return { active: false, count: 0 }
  }
}

function write(state: SessionState) {
  if (!state.active) {
    sessionStorage.removeItem(SESSION_KEY)
  } else {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(state))
  }
  notify()
}

// --- Provider ---

export function EvaluationSessionProvider({ children }: { children: React.ReactNode }) {
  const raw = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot)
  const { active: isSessionActive, count: completedCount } = parse(raw)

  const startSession = useCallback(() => {
    write({ active: true, count: 0 })
  }, [])

  const submitAndAdvance = useCallback((): { sessionComplete: boolean } => {
    const { count } = parse(getSnapshot())
    const newCount = Math.min(count + 1, SESSION_GOAL)
    write({ active: true, count: newCount })
    return { sessionComplete: newCount >= SESSION_GOAL }
  }, [])

  const endSession = useCallback(() => {
    write({ active: false, count: 0 })
  }, [])

  const value: EvaluationSessionContextType = {
    isSessionActive,
    completedCount,
    sessionGoal: SESSION_GOAL,
    startSession,
    submitAndAdvance,
    endSession,
  }

  return (
    <EvaluationSessionContext.Provider value={value}>{children}</EvaluationSessionContext.Provider>
  )
}

export function useEvaluationSession() {
  const context = useContext(EvaluationSessionContext)
  if (context === undefined) {
    throw new Error('useEvaluationSession must be used within an EvaluationSessionProvider')
  }
  return context
}
