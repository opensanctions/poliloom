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

interface PoliticiansContextType {
  currentPolitician: Politician | null;
  loading: boolean;
  error: string | null;
  moveToNext: () => void;
  refetch: () => void;
}

const PoliticiansContext = createContext<
  PoliticiansContextType | undefined
>(undefined);

export function PoliticiansProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const { session, isAuthenticated } = useAuthSession();
  const { preferences, initialized } = usePreferencesContext();
  const [currentPolitician, setCurrentPolitician] = useState<Politician | null>(null);
  const [nextPolitician, setNextPolitician] = useState<Politician | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  const buildQueryParams = useCallback((limit: number = 1) => {
    const params = new URLSearchParams({ limit: limit.toString() });
    languagePreferences.forEach((qid) => params.append("languages", qid));
    countryPreferences.forEach((qid) => params.append("countries", qid));
    return params;
  }, [languagePreferences, countryPreferences]);

  const fetchPoliticians = useCallback(async (limit: number = 1): Promise<Politician[]> => {
    if (!session?.accessToken) return [];

    const params = buildQueryParams(limit);
    const response = await fetch(`/api/politicians?${params.toString()}`);

    if (!response.ok) {
      throw new Error(`Failed to fetch politicians: ${response.statusText}`);
    }

    return response.json();
  }, [session?.accessToken, buildQueryParams]);

  // Clear politicians when preferences change
  useEffect(() => {
    setCurrentPolitician(null);
    setNextPolitician(null);
    setError(null);
  }, [languagePreferences, countryPreferences]);

  // Initial fetch: load current + next (2 politicians)
  useEffect(() => {
    if (!isAuthenticated || !initialized || loading) return;
    if (currentPolitician !== null) return;

    const initialFetch = async () => {
      setLoading(true);
      setError(null);

      try {
        const politicians = await fetchPoliticians(2);

        if (politicians.length === 0) {
          setError("No politicians available. Please try different preferences or try again later.");
        } else {
          setCurrentPolitician(politicians[0]);
          setNextPolitician(politicians[1] || null);
        }
      } catch (err) {
        console.error("Error fetching politicians:", err);
        setError("Failed to load politician data. Please try again.");
      } finally {
        setLoading(false);
      }
    };

    initialFetch();
  }, [
    isAuthenticated,
    initialized,
    loading,
    fetchPoliticians,
    currentPolitician,
  ]);

  const moveToNext = useCallback(() => {
    // Immediately show the next politician
    setCurrentPolitician(nextPolitician);
    setNextPolitician(null);

    // Fetch a new next politician in the background
    const fetchNext = async () => {
      try {
        const politicians = await fetchPoliticians(1);
        if (politicians.length > 0) {
          setNextPolitician(politicians[0]);
        }
      } catch (err) {
        console.error("Error fetching next politician:", err);
        // Don't set error here - user can continue with current politician
      }
    };

    fetchNext();
  }, [nextPolitician, fetchPoliticians]);

  const refetch = useCallback(() => {
    setCurrentPolitician(null);
    setNextPolitician(null);
    setError(null);
  }, []);

  const value: PoliticiansContextType = {
    currentPolitician,
    loading,
    error,
    moveToNext,
    refetch,
  };

  return (
    <PoliticiansContext.Provider value={value}>
      {children}
    </PoliticiansContext.Provider>
  );
}

export function usePoliticians() {
  const context = useContext(PoliticiansContext);
  if (context === undefined) {
    throw new Error(
      "usePoliticians must be used within a PoliticiansProvider"
    );
  }
  return context;
}
