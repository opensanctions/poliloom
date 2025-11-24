import React, { ReactElement } from 'react'
import { render, RenderOptions } from '@testing-library/react'
import { ArchivedPageProvider } from '@/contexts/ArchivedPageContext'
import { EvaluationFiltersProvider } from '@/contexts/EvaluationFiltersContext'
import { EvaluationProvider } from '@/contexts/EvaluationContext'

// Mock SessionProvider for testing
const MockSessionProvider = ({ children }: { children: React.ReactNode }) => <>{children}</>

const AllTheProviders = ({ children }: { children: React.ReactNode }) => {
  return (
    <MockSessionProvider>
      <EvaluationFiltersProvider>
        <EvaluationProvider>
          <ArchivedPageProvider>{children}</ArchivedPageProvider>
        </EvaluationProvider>
      </EvaluationFiltersProvider>
    </MockSessionProvider>
  )
}

const customRender = (ui: ReactElement, options?: Omit<RenderOptions, 'wrapper'>) =>
  render(ui, { wrapper: AllTheProviders, ...options })

export * from '@testing-library/react'
export { customRender as render }
