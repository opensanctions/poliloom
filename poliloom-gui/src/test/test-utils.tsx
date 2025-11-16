import React, { ReactElement } from 'react'
import { render, RenderOptions } from '@testing-library/react'
import { ArchivedPageProvider } from '@/contexts/ArchivedPageContext'
import { PreferencesProvider } from '@/contexts/PreferencesContext'
import { EvaluationProvider } from '@/contexts/EvaluationContext'

// Mock SessionProvider for testing
const MockSessionProvider = ({ children }: { children: React.ReactNode }) => <>{children}</>

const AllTheProviders = ({ children }: { children: React.ReactNode }) => {
  return (
    <MockSessionProvider>
      <PreferencesProvider>
        <EvaluationProvider>
          <ArchivedPageProvider>{children}</ArchivedPageProvider>
        </EvaluationProvider>
      </PreferencesProvider>
    </MockSessionProvider>
  )
}

const customRender = (ui: ReactElement, options?: Omit<RenderOptions, 'wrapper'>) =>
  render(ui, { wrapper: AllTheProviders, ...options })

export * from '@testing-library/react'
export { customRender as render }
