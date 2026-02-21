import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { EvaluationSessionProvider, useEvaluationSession } from './EvaluationSessionContext'

describe('EvaluationSessionContext', () => {
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <EvaluationSessionProvider>{children}</EvaluationSessionProvider>
  )

  beforeEach(() => {
    sessionStorage.clear()
  })

  it('starts with inactive session and zero count', () => {
    const { result } = renderHook(() => useEvaluationSession(), { wrapper })

    expect(result.current.isSessionActive).toBe(false)
    expect(result.current.completedCount).toBe(0)
    expect(result.current.sessionGoal).toBe(5)
  })

  it('activates session on startSession', () => {
    const { result } = renderHook(() => useEvaluationSession(), { wrapper })

    act(() => {
      result.current.startSession()
    })

    expect(result.current.isSessionActive).toBe(true)
    expect(result.current.completedCount).toBe(0)
  })

  it('increments count on submitAndAdvance', () => {
    const { result } = renderHook(() => useEvaluationSession(), { wrapper })

    act(() => {
      result.current.startSession()
    })

    let response: { sessionComplete: boolean }
    act(() => {
      response = result.current.submitAndAdvance()
    })

    expect(result.current.completedCount).toBe(1)
    expect(response!.sessionComplete).toBe(false)
  })

  it('returns sessionComplete when goal reached', () => {
    const { result } = renderHook(() => useEvaluationSession(), { wrapper })

    act(() => {
      result.current.startSession()
    })

    // Submit 4 times
    for (let i = 0; i < 4; i++) {
      act(() => {
        result.current.submitAndAdvance()
      })
    }

    expect(result.current.completedCount).toBe(4)

    let response: { sessionComplete: boolean }
    act(() => {
      response = result.current.submitAndAdvance()
    })

    expect(result.current.completedCount).toBe(5)
    expect(response!.sessionComplete).toBe(true)
  })

  it('resets on endSession', () => {
    const { result } = renderHook(() => useEvaluationSession(), { wrapper })

    act(() => {
      result.current.startSession()
    })
    act(() => {
      result.current.submitAndAdvance()
    })

    expect(result.current.isSessionActive).toBe(true)
    expect(result.current.completedCount).toBe(1)

    act(() => {
      result.current.endSession()
    })

    expect(result.current.isSessionActive).toBe(false)
    expect(result.current.completedCount).toBe(0)
  })
})
