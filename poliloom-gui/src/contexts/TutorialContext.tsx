'use client'

import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useSyncExternalStore,
} from 'react'

const TUTORIAL_COMPLETED_KEY = 'poliloom_tutorial_completed'

// Use useSyncExternalStore to read localStorage without setState in effect
function getSnapshot(): boolean {
  if (typeof window === 'undefined') return true // SSR default
  return localStorage.getItem(TUTORIAL_COMPLETED_KEY) === 'true'
}

function getServerSnapshot(): boolean {
  return true // Default to true on server to prevent flash
}

function subscribe(callback: () => void): () => void {
  window.addEventListener('storage', callback)
  return () => window.removeEventListener('storage', callback)
}

interface TutorialContextType {
  hasCompletedTutorial: boolean
  completeTutorial: () => void
  resetTutorial: () => void
}

const TutorialContext = createContext<TutorialContextType | undefined>(undefined)

export function TutorialProvider({ children }: { children: React.ReactNode }) {
  const hasCompletedTutorial = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot)
  const [, forceUpdate] = useState(0)

  const completeTutorial = useCallback(() => {
    localStorage.setItem(TUTORIAL_COMPLETED_KEY, 'true')
    forceUpdate((n) => n + 1) // Trigger re-render to pick up new localStorage value
  }, [])

  const resetTutorial = useCallback(() => {
    localStorage.removeItem(TUTORIAL_COMPLETED_KEY)
    forceUpdate((n) => n + 1) // Trigger re-render to pick up new localStorage value
  }, [])

  const value: TutorialContextType = {
    hasCompletedTutorial,
    completeTutorial,
    resetTutorial,
  }

  return <TutorialContext.Provider value={value}>{children}</TutorialContext.Provider>
}

export function useTutorial() {
  const context = useContext(TutorialContext)
  if (context === undefined) {
    throw new Error('useTutorial must be used within a TutorialProvider')
  }
  return context
}
