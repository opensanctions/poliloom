"use client"

import { useSession, signOut } from "next-auth/react"
import Link from "next/link"
import { handleSignIn } from "@/lib/actions"

export function Header() {
  const { data: session, status } = useSession()

  return (
    <header className="bg-white shadow-sm border-b">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          <div className="flex items-center">
            <Link href="/" className="text-xl font-bold text-gray-900">
              PoliLoom
            </Link>
          </div>
          
          <div className="flex items-center space-x-4">
            {status === "loading" && (
              <div className="text-sm text-gray-500">Loading...</div>
            )}
            
            {status === "authenticated" && session?.user && (
              <>
                <div className="text-sm text-gray-700">
                  Welcome, {session.user.name || session.user.email}
                </div>
                <button
                  onClick={() => signOut()}
                  className="text-sm text-gray-500 hover:text-gray-700 font-medium"
                >
                  Sign out
                </button>
              </>
            )}
            
            {status === "unauthenticated" && (
              <form action={handleSignIn}>
                <button
                  type="submit"
                  className="text-sm text-indigo-600 hover:text-indigo-500 font-medium"
                >
                  Sign in
                </button>
              </form>
            )}
          </div>
        </div>
      </div>
    </header>
  )
}