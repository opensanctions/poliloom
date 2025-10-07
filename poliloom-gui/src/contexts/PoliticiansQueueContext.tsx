"use client";

import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  useMemo,
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
  const [needsEnrichment, setNeedsEnrichment] = useState(false);

  // Memoize preference arrays to prevent unnecessary recreations
  const languagePreferences = useMemo(
    () =>
      preferences
        .filter((p) => p.preference_type === PreferenceType.LANGUAGE)
        .map((p) => p.wikidata_id),
    [preferences]
  );

  const countryPreferences = useMemo(
    () =>
      preferences
        .filter((p) => p.preference_type === PreferenceType.COUNTRY)
        .map((p) => p.wikidata_id),
    [preferences]
  );

  const buildQueryParams = useCallback(() => {
    const params = new URLSearchParams({ limit: QUEUE_SIZE.toString() });
    languagePreferences.forEach((qid) => params.append("languages", qid));
    countryPreferences.forEach((qid) => params.append("countries", qid));
    return params;
  }, [languagePreferences, countryPreferences]);

  const fetchPoliticians = useCallback(async (): Promise<Politician[]> => {
    if (!session?.accessToken) return [];

    const params = buildQueryParams();
    const response = await fetch(`/api/politicians?${params.toString()}`);

    if (!response.ok) {
      throw new Error(`Failed to fetch politicians: ${response.statusText}`);
    }

    return response.json();
  }, [session?.accessToken, buildQueryParams]);

  const triggerEnrichment = useCallback(async (): Promise<void> => {
    if (!session?.accessToken) return;

    const params = buildQueryParams();
    const response = await fetch(`/api/enrich?${params.toString()}`, {
      method: "POST",
    });

    if (!response.ok) {
      throw new Error(`Failed to enrich politicians: ${response.statusText}`);
    }
  }, [session?.accessToken, buildQueryParams]);

  // Clear queue when preferences change
  useEffect(() => {
    setQueue([]);
    setError(null);
    setNeedsEnrichment(false);
  }, [languagePreferences, countryPreferences]);

  // Fetch politicians when queue is low
  useEffect(() => {
    if (!isAuthenticated || !initialized || loading || enriching) return;
    if (queue.length >= REFETCH_THRESHOLD) return;

    const fetchMore = async () => {
      setLoading(true);
      setError(null);

      try {
        const politicians = await fetchPoliticians();

        if (politicians.length === 0) {
          if (!needsEnrichment) {
            setNeedsEnrichment(true);
          } else {
            setError("No politicians available. Please try different preferences or try again later.");
          }
        } else {
          setQueue((prev) => [...prev, ...politicians]);
          setNeedsEnrichment(false);
        }
      } catch (err) {
        console.error("Error fetching politicians:", err);
        setError("Failed to load politician data. Please try again.");
      } finally {
        setLoading(false);
      }
    };

    fetchMore();
  }, [
    queue.length,
    isAuthenticated,
    initialized,
    loading,
    enriching,
    needsEnrichment,
    fetchPoliticians,
  ]);

  // Trigger enrichment when needed
  useEffect(() => {
    if (!needsEnrichment || enriching || !isAuthenticated) return;

    const enrich = async () => {
      setEnriching(true);
      setError(null);

      try {
        await triggerEnrichment();
        // After enrichment, fetch will be triggered by the effect above
      } catch (err) {
        console.error("Error enriching politicians:", err);
        setError("Failed to enrich politicians. Please try again later.");
        setNeedsEnrichment(false);
      } finally {
        setEnriching(false);
      }
    };

    enrich();
  }, [needsEnrichment, enriching, isAuthenticated, triggerEnrichment]);

  const nextPolitician = useCallback(() => {
    setQueue((prev) => prev.slice(1));
  }, []);

  const refetch = useCallback(() => {
    setQueue([]);
    setError(null);
    setNeedsEnrichment(false);
  }, []);

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
      "usePoliticiansQueue must be used within a PoliticiansQueueProvider"
    );
  }
  return context;
}
