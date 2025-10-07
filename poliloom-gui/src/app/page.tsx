"use client";

import { useAuthSession } from "@/hooks/useAuthSession";
import { Header } from "@/components/Header";
import { PoliticianEvaluation } from "@/components/PoliticianEvaluation";
import { handleSignIn } from "@/lib/actions";
import { usePoliticiansQueue } from "@/contexts/PoliticiansQueueContext";

export default function Home() {
  const { session, status, isAuthenticated } = useAuthSession();
  const { currentPolitician, queueLength, loading, enriching, error, nextPolitician, refetch } = usePoliticiansQueue();

  return (
    <>
      <Header />

      {currentPolitician && session?.accessToken ? (
        <PoliticianEvaluation politician={currentPolitician} onNext={nextPolitician} />
      ) : (
        <main className="bg-gray-50 grid place-items-center py-12 px-4 sm:px-6 lg:px-8 min-h-0 overflow-y-auto">
          <div className="text-center max-w-2xl">
            <h1 className="text-4xl font-bold text-gray-900 mb-4">
              PoliLoom Data Evaluation
            </h1>
            <p className="text-lg text-gray-600 mb-8">
              Help evaluate politician data extracted from Wikipedia and other
              sources
            </p>

            {status === "loading" && (
              <div className="text-gray-500">
                Loading authentication status...
              </div>
            )}

            {status === "unauthenticated" && (
              <div className="space-y-4">
                <p className="text-gray-600">
                  Please sign in with your MediaWiki account to start evaluating
                  data.
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

                {enriching && (
                  <div className="bg-purple-50 border border-purple-200 rounded-md p-4">
                    <p className="text-purple-800">
                      No politicians available with your current preferences.
                      Enriching data for you...
                    </p>
                  </div>
                )}

                {error && (
                  <div className="bg-red-50 border border-red-200 rounded-md p-4">
                    <p className="text-red-800">{error}</p>
                    <button
                      onClick={refetch}
                      className="mt-2 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700"
                    >
                      Try Again
                    </button>
                  </div>
                )}

                {!loading && !enriching && !error && !currentPolitician && (
                  <div className="bg-gray-50 border border-gray-200 rounded-md p-4">
                    <p className="text-gray-600">
                      No politicians available. Check your{" "}
                      <a
                        href="/preferences"
                        className="text-gray-700 hover:text-gray-900 underline"
                      >
                        preferences
                      </a>{" "}
                      or wait for new data.
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>
        </main>
      )}
    </>
  );
}
