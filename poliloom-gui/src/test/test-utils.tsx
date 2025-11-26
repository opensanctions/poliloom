import React, { ReactElement } from 'react'
import { render, RenderOptions } from '@testing-library/react'
import { EvaluationFiltersProvider } from '@/contexts/EvaluationFiltersContext'
import { EvaluationProvider } from '@/contexts/EvaluationContext'
import { TutorialProvider } from '@/contexts/TutorialContext'

// Mock SessionProvider for testing
const MockSessionProvider = ({ children }: { children: React.ReactNode }) => <>{children}</>

const AllTheProviders = ({ children }: { children: React.ReactNode }) => {
  return (
    <MockSessionProvider>
      <TutorialProvider>
        <EvaluationFiltersProvider>
          <EvaluationProvider>{children}</EvaluationProvider>
        </EvaluationFiltersProvider>
      </TutorialProvider>
    </MockSessionProvider>
  )
}

const customRender = (ui: ReactElement, options?: Omit<RenderOptions, 'wrapper'>) =>
  render(ui, { wrapper: AllTheProviders, ...options })

export * from '@testing-library/react'
export { customRender as render }
