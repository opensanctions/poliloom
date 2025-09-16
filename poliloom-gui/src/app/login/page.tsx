"use client"

import { signIn } from "next-auth/react"
import { useEffect } from "react"
import { useSearchParams } from "next/navigation"

export default function LoginPage() {
  const searchParams = useSearchParams()

  useEffect(() => {
    // Get the callback URL from NextAuth or default to home
    const callbackUrl = searchParams.get("callbackUrl") || "/"

    // Immediately redirect to MediaWiki OAuth without showing any UI
    signIn("wikimedia", { callbackUrl })
  }, [searchParams])

  // Show minimal loading state while redirecting
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
        <p className="mt-2 text-gray-600">Redirecting to MediaWiki login...</p>
      </div>
    </div>
  )
}