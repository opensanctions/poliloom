"use client";

import { createContext, useContext, useState, ReactNode, useCallback } from 'react';

interface ArchivedPageContextType {
  loadedPages: Set<string>;
  markPageAsLoaded: (pageId: string) => void;
  isPageLoaded: (pageId: string) => boolean;
  clearLoadedPages: () => void;
}

const ArchivedPageContext = createContext<ArchivedPageContextType | undefined>(undefined);

interface ArchivedPageProviderProps {
  children: ReactNode;
}

export function ArchivedPageProvider({ children }: ArchivedPageProviderProps) {
  const [loadedPages, setLoadedPages] = useState<Set<string>>(new Set());

  const markPageAsLoaded = useCallback((pageId: string) => {
    setLoadedPages(prev => new Set(prev).add(pageId));
  }, []);

  const isPageLoaded = useCallback((pageId: string) => {
    return loadedPages.has(pageId);
  }, [loadedPages]);

  const clearLoadedPages = useCallback(() => {
    setLoadedPages(new Set());
  }, []);

  const value: ArchivedPageContextType = {
    loadedPages,
    markPageAsLoaded,
    isPageLoaded,
    clearLoadedPages
  };

  return (
    <ArchivedPageContext.Provider value={value}>
      {children}
    </ArchivedPageContext.Provider>
  );
}

export function useArchivedPageCache() {
  const context = useContext(ArchivedPageContext);
  
  if (context === undefined) {
    throw new Error('useArchivedPageCache must be used within an ArchivedPageProvider');
  }
  
  return context;
}