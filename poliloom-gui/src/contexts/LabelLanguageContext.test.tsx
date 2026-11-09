import { describe, it, expect } from 'vitest'
import { renderHook } from '@testing-library/react'
import { LabelLanguageProvider, useLabelLanguages } from './LabelLanguageContext'

describe('LabelLanguageContext', () => {
  it('exposes the provided language codes', () => {
    const { result } = renderHook(() => useLabelLanguages(), {
      wrapper: ({ children }) => (
        <LabelLanguageProvider languages={['sv', 'en']}>{children}</LabelLanguageProvider>
      ),
    })
    expect(result.current).toEqual(['sv', 'en'])
  })

  it('throws when used outside provider', () => {
    expect(() => renderHook(() => useLabelLanguages())).toThrow(
      'useLabelLanguages must be used within a LabelLanguageProvider',
    )
  })
})
