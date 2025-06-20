"use client"

import { useSession } from "next-auth/react"
import { Header } from "@/components/Header"
import { handleSignIn } from "@/lib/actions"

export default function Home() {
  const { data: session, status } = useSession()

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      
      <main className="max-w-4xl mx-auto py-12 px-4 sm:px-6 lg:px-8">
        <div className="text-center">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            PoliLoom Data Confirmation
          </h1>
          <p className="text-lg text-gray-600 mb-8">
            Help verify politician data extracted from Wikipedia and other sources
          </p>
          
          {status === "loading" && (
            <div className="text-gray-500">Loading authentication status...</div>
          )}
          
          {status === "unauthenticated" && (
            <div className="space-y-4">
              <p className="text-gray-600">
                Please sign in with your MediaWiki account to start confirming data.
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
              <div className="bg-green-50 border border-green-200 rounded-md p-4">
                <p className="text-green-800">
                  ✅ You're signed in as {session?.user?.name || session?.user?.email}
                </p>
              </div>
              
              <div className="bg-white shadow rounded-lg p-6">
                <h2 className="text-xl font-semibold text-gray-900 mb-4">
                  Ready to confirm politician data
                </h2>
                <p className="text-gray-600 mb-4">
                  The confirmation interface will be available here once politician data is loaded from the API.
                </p>
                <button
                  className="px-4 py-2 bg-gray-300 text-gray-500 rounded-md cursor-not-allowed"
                  disabled
                >
                  Start Confirming (Coming Soon)
                </button>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
