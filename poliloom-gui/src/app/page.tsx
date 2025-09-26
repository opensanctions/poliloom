"use client"

import { useAuthSession } from "@/hooks/useAuthSession"
import { useState, useEffect, useCallback } from "react"
import { Header } from "@/components/Header"
import { PoliticianEvaluation } from "@/components/PoliticianEvaluation"
import { handleSignIn } from "@/lib/actions"
import { usePreferencesContext } from "@/contexts/PreferencesContext"
import { Politician } from "@/types"

export default function Home() {
  const { session, status, isAuthenticated } = useAuthSession()
  const { languagePreferences, countryPreferences } = usePreferencesContext()
  const [politician, setPolitician] = useState<Politician | null>(null)
  const [nextPolitician, setNextPolitician] = useState<Politician | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchPolitician = useCallback(async (): Promise<Politician | null> => {
    if (!session?.accessToken) return null

    // Build query parameters with preferences
    const params = new URLSearchParams({ limit: '1' })

    if (languagePreferences.length > 0) {
      languagePreferences.forEach(qid => params.append('languages', qid))
    }

    if (countryPreferences.length > 0) {
      countryPreferences.forEach(qid => params.append('countries', qid))
    }

    const response = await fetch(`/api/politicians/?${params.toString()}`)
    if (!response.ok) {
      throw new Error(`Failed to fetch politician: ${response.statusText}`)
    }
    const politicians: Politician[] = await response.json()
    return politicians.length > 0 ? politicians[0] : null
  }, [session?.accessToken, languagePreferences, countryPreferences])

  const loadInitialData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const politician = await fetchPolitician()
      setPolitician(politician)
      
      // Pre-load next politician in background
      if (politician) {
        fetchPolitician()
          .then(setNextPolitician)
          .catch(() => setNextPolitician(null))
      }
    } catch (error) {
      console.error('Error fetching politicians:', error)
      setError('Failed to load politician data. Please try again.')
    } finally {
      setLoading(false)
    }
  }, [fetchPolitician])

  useEffect(() => {
    if (isAuthenticated && session?.accessToken) {
      loadInitialData()
    }
  }, [isAuthenticated, session?.accessToken, loadInitialData])

  const handleNext = () => {
    if (!nextPolitician) return

    // Show next politician immediately
    setPolitician(nextPolitician)
    
    // Pre-load another politician in background
    fetchPolitician()
      .then(setNextPolitician)
      .catch(() => setNextPolitician(null))
  }

  return (
    <>
      <Header />
      
      {politician && session?.accessToken ? (
        <PoliticianEvaluation
          politician={politician}
          onNext={handleNext}
        />
      ) : (
        <main className="bg-gray-50 grid place-items-center py-12 px-4 sm:px-6 lg:px-8 min-h-0 overflow-y-auto">
          <div className="text-center max-w-2xl">
            <h1 className="text-4xl font-bold text-gray-900 mb-4">
              PoliLoom Data Evaluation
            </h1>
            <p className="text-lg text-gray-600 mb-8">
              Help evaluate politician data extracted from Wikipedia and other sources
            </p>
            
            {status === "loading" && (
              <div className="text-gray-500">Loading authentication status...</div>
            )}
            
            {status === "unauthenticated" && (
              <div className="space-y-4">
                <p className="text-gray-600">
                  Please sign in with your MediaWiki account to start evaluating data.
                </p>
                <form action={handleSignIn}>
                  <button
                    type="submit"
                    className="inline-flex items-center px-6 py-3 border border-transparent text-base font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700"
                  >
                    Sign in with MediaWiki
                  </button>
                </form>
              </div>
            )}
            
            {isAuthenticated && (
              <div className="space-y-6">
                {loading && (
                  <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
                    <p className="text-blue-800">Loading politician data...</p>
                  </div>
                )}
                
                {error && (
                  <div className="bg-red-50 border border-red-200 rounded-md p-4">
                    <p className="text-red-800">{error}</p>
                    <button
                      onClick={loadInitialData}
                      className="mt-2 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700"
                    >
                      Try Again
                    </button>
                  </div>
                )}
                
                {!loading && !error && !politician && (
                  <div className="bg-gray-50 border border-gray-200 rounded-md p-4">
                    <p className="text-gray-600">No politicians available for evaluation at this time.</p>
                  </div>
                )}
              </div>
            )}
          </div>
        </main>
      )}
    </>
  )
}
