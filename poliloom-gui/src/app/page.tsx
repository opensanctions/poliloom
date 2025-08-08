"use client"

import { useSession } from "next-auth/react"
import { useState, useEffect, useCallback } from "react"
import { Header } from "@/components/Header"
import { PoliticianEvaluation } from "@/components/PoliticianEvaluation"
import { handleSignIn } from "@/lib/actions"
import { fetchUnconfirmedPolitician } from "@/lib/api"
import { Politician } from "@/types"

export default function Home() {
  const { data: session, status } = useSession()
  const [politician, setPolitician] = useState<Politician | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadPolitician = useCallback(async () => {
    if (!session?.accessToken) return

    setLoading(true)
    setError(null)
    try {
      const data = await fetchUnconfirmedPolitician(session.accessToken)
      setPolitician(data)
    } catch (error) {
      console.error('Error fetching politician:', error)
      setError('Failed to load politician data. Please try again.')
    } finally {
      setLoading(false)
    }
  }, [session?.accessToken])

  useEffect(() => {
    if (status === 'authenticated' && session?.accessToken) {
      loadPolitician()
    }
  }, [status, session?.accessToken, loadPolitician])

  const handleNext = () => {
    setPolitician(null)
    loadPolitician()
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      
      <main className="py-12 px-4 sm:px-6 lg:px-8">
        <div className="text-center">
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
          
          {status === "authenticated" && (
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
                    onClick={loadPolitician}
                    className="mt-2 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700"
                  >
                    Try Again
                  </button>
                </div>
              )}
              
              {politician && session?.accessToken && (
                <PoliticianEvaluation
                  politician={politician}
                  accessToken={session.accessToken}
                  onNext={handleNext}
                />
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
    </div>
  )
}
