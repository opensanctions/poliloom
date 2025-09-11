import { useSession, signIn } from "next-auth/react"
import { useEffect } from "react"

export function useAuthSession() {
  const { data: session, status } = useSession()
  
  useEffect(() => {
    if (session?.error === "RefreshAccessTokenError") {
      // Force sign in to resolve error
      signIn()
    }
  }, [session])
  
  return { 
    session, 
    status, 
    isAuthenticated: status === "authenticated" && !session?.error 
  }
}