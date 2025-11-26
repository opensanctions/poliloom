'use client'

import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useSyncExternalStore,
} from 'react'

const BASIC_TUTORIAL_KEY = 'poliloom_basic_tutorial_completed'
const ADVANCED_TUTORIAL_KEY = 'poliloom_advanced_tutorial_completed'

function subscribe(callback: () => void): () => void {
  window.addEventListener('storage', callback)
  return () => window.removeEventListener('storage', callback)
}

function createLocalStorageSnapshot(key: string, serverDefault: boolean) {
  return {
    getSnapshot: () => {
      if (typeof window === 'undefined') return serverDefault
      return localStorage.getItem(key) === 'true'
    },
    getServerSnapshot: () => serverDefault,
  }
}

const basicTutorialStorage = createLocalStorageSnapshot(BASIC_TUTORIAL_KEY, true)
const advancedTutorialStorage = createLocalStorageSnapshot(ADVANCED_TUTORIAL_KEY, true)

interface TutorialContextType {
  hasCompletedBasicTutorial: boolean
  hasCompletedAdvancedTutorial: boolean
  completeBasicTutorial: () => void
  completeAdvancedTutorial: () => void
  resetTutorial: () => void
}

export const TutorialContext = createContext<TutorialContextType | undefined>(undefined)

export function TutorialProvider({ children }: { children: React.ReactNode }) {
  const hasCompletedBasicTutorial = useSyncExternalStore(
    subscribe,
    basicTutorialStorage.getSnapshot,
    basicTutorialStorage.getServerSnapshot,
  )
  const hasCompletedAdvancedTutorial = useSyncExternalStore(
    subscribe,
    advancedTutorialStorage.getSnapshot,
    advancedTutorialStorage.getServerSnapshot,
  )
  const [, forceUpdate] = useState(0)

  const completeBasicTutorial = useCallback(() => {
    localStorage.setItem(BASIC_TUTORIAL_KEY, 'true')
    forceUpdate((n) => n + 1)
  }, [])

  const completeAdvancedTutorial = useCallback(() => {
    localStorage.setItem(ADVANCED_TUTORIAL_KEY, 'true')
    forceUpdate((n) => n + 1)
  }, [])

  const resetTutorial = useCallback(() => {
    localStorage.removeItem(BASIC_TUTORIAL_KEY)
    localStorage.removeItem(ADVANCED_TUTORIAL_KEY)
    forceUpdate((n) => n + 1)
  }, [])

  const value: TutorialContextType = {
    hasCompletedBasicTutorial,
    hasCompletedAdvancedTutorial,
    completeBasicTutorial,
    completeAdvancedTutorial,
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
