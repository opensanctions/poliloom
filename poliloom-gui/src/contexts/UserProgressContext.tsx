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
const STATS_UNLOCKED_KEY = 'poliloom_stats_unlocked'

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
const statsUnlockedStorage = createLocalStorageSnapshot(STATS_UNLOCKED_KEY, false)

interface UserProgressContextType {
  hasCompletedBasicTutorial: boolean
  hasCompletedAdvancedTutorial: boolean
  statsUnlocked: boolean
  completeBasicTutorial: () => void
  completeAdvancedTutorial: () => void
  unlockStats: () => void
}

export const UserProgressContext = createContext<UserProgressContextType | undefined>(undefined)

export function UserProgressProvider({ children }: { children: React.ReactNode }) {
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
  const statsUnlocked = useSyncExternalStore(
    subscribe,
    statsUnlockedStorage.getSnapshot,
    statsUnlockedStorage.getServerSnapshot,
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

  const unlockStats = useCallback(() => {
    localStorage.setItem(STATS_UNLOCKED_KEY, 'true')
    forceUpdate((n) => n + 1)
  }, [])

  const value: UserProgressContextType = {
    hasCompletedBasicTutorial,
    hasCompletedAdvancedTutorial,
    statsUnlocked,
    completeBasicTutorial,
    completeAdvancedTutorial,
    unlockStats,
  }

  return <UserProgressContext.Provider value={value}>{children}</UserProgressContext.Provider>
}

export function useUserProgress() {
  const context = useContext(UserProgressContext)
  if (context === undefined) {
    throw new Error('useUserProgress must be used within a UserProgressProvider')
  }
  return context
}

// Backwards compatibility aliases
export const TutorialContext = UserProgressContext
export const TutorialProvider = UserProgressProvider
export const useTutorial = useUserProgress
