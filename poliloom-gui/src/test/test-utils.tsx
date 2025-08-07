import React, { ReactElement } from 'react';
import { render, RenderOptions } from '@testing-library/react';
import { ArchivedPageCacheProvider } from '@/contexts/ArchivedPageContext';

// Mock SessionProvider for testing
const MockSessionProvider = ({ children }: { children: React.ReactNode }) => <>{children}</>;

const AllTheProviders = ({ children }: { children: React.ReactNode }) => {
  return (
    <MockSessionProvider>
      <ArchivedPageCacheProvider>
        {children}
      </ArchivedPageCacheProvider>
    </MockSessionProvider>
  );
};

const customRender = (
  ui: ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>,
) => render(ui, { wrapper: AllTheProviders, ...options });

export * from '@testing-library/react';
export { customRender as render };