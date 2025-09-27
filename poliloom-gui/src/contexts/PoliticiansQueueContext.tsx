"use client";

import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
} from "react";
import { Politician } from "@/types";
import { useAuthSession } from "@/hooks/useAuthSession";
import { usePreferencesContext } from "./PreferencesContext";

interface PoliticiansQueueContextType {
  currentPolitician: Politician | null;
  queueLength: number;
  loading: boolean;
  error: string | null;
  nextPolitician: () => void;
  refetch: () => void;
}

const PoliticiansQueueContext = createContext<
  PoliticiansQueueContextType | undefined
>(undefined);

const QUEUE_SIZE = 5;
const REFETCH_THRESHOLD = 2;

export function PoliticiansQueueProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const { session, isAuthenticated } = useAuthSession();
  const { languagePreferences, countryPreferences, initialized } =
    usePreferencesContext();
  const [queue, setQueue] = useState<Politician[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchPoliticians = useCallback(
    async (limit: number = QUEUE_SIZE): Promise<Politician[]> => {
      if (!session?.accessToken) return [];

      // Build query parameters with preferences
      const params = new URLSearchParams({ limit: limit.toString() });

      if (languagePreferences.length > 0) {
        languagePreferences.forEach((qid) => params.append("languages", qid));
      }

      if (countryPreferences.length > 0) {
        countryPreferences.forEach((qid) => params.append("countries", qid));
      }

      const response = await fetch(`/api/politicians?${params.toString()}`);
      if (!response.ok) {
        throw new Error(`Failed to fetch politicians: ${response.statusText}`);
      }

      const politicians: Politician[] = await response.json();
      return politicians;
    },
    [session?.accessToken, languagePreferences, countryPreferences],
  );

  const loadPoliticians = useCallback(
    async (append: boolean = false) => {
      if (!isAuthenticated || !initialized) return;

      setLoading(true);
      setError(null);

      try {
        const politicians = await fetchPoliticians();
        setQueue((prev) => (append ? [...prev, ...politicians] : politicians));
      } catch (error) {
        console.error("Error fetching politicians:", error);
        setError("Failed to load politician data. Please try again.");
      } finally {
        setLoading(false);
      }
    },
    [isAuthenticated, initialized, fetchPoliticians],
  );

  // Initial load when authenticated and preferences are initialized
  useEffect(() => {
    if (isAuthenticated && initialized) {
      loadPoliticians();
    }
  }, [isAuthenticated, initialized, languagePreferences, countryPreferences]);

  // Auto-refetch when queue gets low
  useEffect(() => {
    if (
      queue.length === REFETCH_THRESHOLD &&
      !loading &&
      isAuthenticated &&
      initialized
    ) {
      loadPoliticians(true); // append to existing queue
    }
  }, [queue.length, loading, isAuthenticated, initialized, loadPoliticians]);

  const nextPolitician = useCallback(() => {
    setQueue((prev) => prev.slice(1));
  }, []);

  const refetch = useCallback(() => {
    setQueue([]);
    loadPoliticians();
  }, [loadPoliticians]);

  const value: PoliticiansQueueContextType = {
    currentPolitician: queue[0] || null,
    queueLength: queue.length,
    loading,
    error,
    nextPolitician,
    refetch,
  };

  return (
    <PoliticiansQueueContext.Provider value={value}>
      {children}
    </PoliticiansQueueContext.Provider>
  );
}

export function usePoliticiansQueue() {
  const context = useContext(PoliticiansQueueContext);
  if (context === undefined) {
    throw new Error(
      "usePoliticiansQueue must be used within a PoliticiansQueueProvider",
    );
  }
  return context;
}
