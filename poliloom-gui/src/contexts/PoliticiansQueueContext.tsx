"use client";

import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  useRef,
} from "react";
import { Politician, PreferenceType } from "@/types";
import { useAuthSession } from "@/hooks/useAuthSession";
import { usePreferencesContext } from "./PreferencesContext";

interface PoliticiansQueueContextType {
  currentPolitician: Politician | null;
  queueLength: number;
  loading: boolean;
  enriching: boolean;
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
  const { preferences, initialized } = usePreferencesContext();
  const [queue, setQueue] = useState<Politician[]>([]);
  const [loading, setLoading] = useState(false);
  const [enriching, setEnriching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const enrichErrorRef = useRef<string | null>(null);

  const languagePreferences = preferences
    .filter(p => p.preference_type === PreferenceType.LANGUAGE)
    .map(p => p.wikidata_id);

  const countryPreferences = preferences
    .filter(p => p.preference_type === PreferenceType.COUNTRY)
    .map(p => p.wikidata_id);

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

  const enrichPoliticians = useCallback(
    async (): Promise<void> => {
      if (!session?.accessToken) return;

      // Build query parameters with preferences
      const params = new URLSearchParams();

      if (languagePreferences.length > 0) {
        languagePreferences.forEach((qid) => params.append("languages", qid));
      }

      if (countryPreferences.length > 0) {
        countryPreferences.forEach((qid) => params.append("countries", qid));
      }

      const response = await fetch(`/api/enrich?${params.toString()}`, {
        method: "POST",
      });

      if (!response.ok) {
        throw new Error(`Failed to enrich politicians: ${response.statusText}`);
      }
    },
    [session?.accessToken, languagePreferences, countryPreferences],
  );

  const loadPoliticians = useCallback(
    async () => {
      if (!isAuthenticated || !initialized) return;

      setLoading(true);
      setError(null);

      try {
        const politicians = await fetchPoliticians();

        // If no politicians returned, try to enrich if we haven't hit an error yet
        if (politicians.length === 0 && !enrichErrorRef.current) {
          setLoading(false);
          setEnriching(true);
          try {
            await enrichPoliticians();
            // After enrichment, try to fetch again
            const enrichedPoliticians = await fetchPoliticians();

            if (enrichedPoliticians.length === 0) {
              const errorMsg = "No politicians available. Please try different preferences or try again later.";
              enrichErrorRef.current = errorMsg;
              setError(errorMsg);
            }

            setQueue((prev) => [...prev, ...enrichedPoliticians]);
          } catch (enrichError) {
            console.error("Error enriching politicians:", enrichError);
            const errorMsg = "Failed to enrich politicians. Please try again later.";
            enrichErrorRef.current = errorMsg;
            setError(errorMsg);
          } finally {
            setEnriching(false);
          }
        } else {
          setQueue((prev) => [...prev, ...politicians]);
          // Clear enrich error if we got politicians
          if (politicians.length > 0) {
            enrichErrorRef.current = null;
          }
        }
      } catch (error) {
        console.error("Error fetching politicians:", error);
        setError("Failed to load politician data. Please try again.");
      } finally {
        setLoading(false);
      }
    },
    [isAuthenticated, initialized, fetchPoliticians, enrichPoliticians],
  );

  // Initial load when authenticated and preferences are initialized
  useEffect(() => {
    if (isAuthenticated && initialized) {
      setQueue([]);
      enrichErrorRef.current = null;
      loadPoliticians();
    }
  }, [isAuthenticated, initialized, preferences]);

  // Auto-refetch when queue gets low or empty
  useEffect(() => {
    if (!loading && !enriching && !error && isAuthenticated && initialized) {
      if (queue.length === 0 || queue.length === REFETCH_THRESHOLD) {
        loadPoliticians();
      }
    }
  }, [queue.length, loading, enriching, error, isAuthenticated, initialized, loadPoliticians]);

  const nextPolitician = useCallback(() => {
    setQueue((prev) => prev.slice(1));
  }, []);

  const refetch = useCallback(() => {
    setQueue([]);
    enrichErrorRef.current = null;
    loadPoliticians();
  }, [loadPoliticians]);

  const value: PoliticiansQueueContextType = {
    currentPolitician: queue[0] || null,
    queueLength: queue.length,
    loading,
    enriching,
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
