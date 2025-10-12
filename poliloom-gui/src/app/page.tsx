'use client'

import { useAuthSession } from '@/hooks/useAuthSession'
import { Header } from '@/components/Header'
import { Button } from '@/components/Button'
import { PoliticianEvaluation } from '@/components/PoliticianEvaluation'
import { handleSignIn } from '@/lib/actions'
import { usePoliticians } from '@/contexts/PoliticiansContext'
import Link from 'next/link'

export default function Home() {
  const { session, status, isAuthenticated } = useAuthSession()
  const { currentPolitician, loading, refetch, loadPoliticians } = usePoliticians()

  return (
    <>
      <Header />

      {currentPolitician && session?.accessToken ? (
        <PoliticianEvaluation
          key={currentPolitician.id}
          politician={currentPolitician}
          onNext={refetch}
        />
      ) : (
        <main className="bg-gray-50 grid place-items-center py-12 px-4 sm:px-6 lg:px-8 min-h-0 overflow-y-auto">
          <div className="text-center max-w-2xl">
            <h1 className="text-4xl font-bold text-gray-900 mb-4">PoliLoom Data Evaluation</h1>
            <p className="text-lg text-gray-600 mb-8">
              Help evaluate politician data extracted from Wikipedia and other sources
            </p>

            {status === 'loading' && (
              <div className="text-gray-500">Loading authentication status...</div>
            )}

            {status === 'unauthenticated' && (
              <div className="space-y-4">
                <p className="text-gray-600">
                  Please sign in with your MediaWiki account to start evaluating data.
                </p>
                <form action={handleSignIn}>
                  <Button type="submit" className="px-6 py-3 text-base">
                    Sign in with MediaWiki
                  </Button>
                </form>
              </div>
            )}

            {isAuthenticated &&
              !currentPolitician &&
              (loading ? (
                <div className="text-gray-500">Loading politician data...</div>
              ) : (
                <div className="bg-gray-50 border border-gray-200 rounded-md p-4">
                  <p className="text-gray-600">
                    Currently no politicians available, we&apos;re enriching more. You can wait a
                    minute, change your filter{' '}
                    <Link
                      href="/preferences"
                      className="text-gray-700 hover:text-gray-900 underline"
                    >
                      preferences
                    </Link>
                    , or{' '}
                    <button
                      onClick={loadPoliticians}
                      className="text-gray-700 hover:text-gray-900 underline cursor-pointer bg-transparent border-0 p-0 font-inherit"
                    >
                      reload
                    </button>
                    .
                  </p>
                </div>
              ))}
          </div>
        </main>
      )}
    </>
  )
}
