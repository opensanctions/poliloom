"use client";

import { useAuthSession } from "@/hooks/useAuthSession";
import { Header } from "@/components/Header";
import { PoliticianEvaluation } from "@/components/PoliticianEvaluation";
import { handleSignIn } from "@/lib/actions";
import { usePoliticians } from "@/contexts/PoliticiansContext";

export default function Home() {
  const { session, status, isAuthenticated } = useAuthSession();
  const { currentPolitician, loading, refetch } = usePoliticians();

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

            {isAuthenticated && !currentPolitician && (
              loading ? (
                <div className="text-gray-500">
                  Loading politician data...
                </div>
              ) : (
                <div className="bg-gray-50 border border-gray-200 rounded-md p-4">
                  <p className="text-gray-600 mb-3">
                    Currently no politicians available, we're enriching more. You can wait a minute or change your filter{" "}
                    <a
                      href="/preferences"
                      className="text-gray-700 hover:text-gray-900 underline"
                    >
                      preferences
                    </a>.
                  </p>
                  <button
                    onClick={refetch}
                    className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700"
                  >
                    Reload
                  </button>
                </div>
              )
            )}
          </div>
        </main>
      )}
    </>
  );
}
