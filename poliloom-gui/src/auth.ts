import NextAuth from "next-auth"
import type { NextAuthConfig } from "next-auth"
import Wikimedia from "next-auth/providers/wikimedia"

export const config = {
  providers: [
    Wikimedia({
      clientId: process.env.MEDIAWIKI_OAUTH_CLIENT_ID!,
      clientSecret: process.env.MEDIAWIKI_OAUTH_CLIENT_SECRET!,
      client: {
        token_endpoint_auth_method: "client_secret_post",
      },
    }),
  ],
  callbacks: {
    async jwt({ token, account }) {
      // First-time login
      if (account) {
        return {
          ...token,
          access_token: account.access_token,
          refresh_token: account.refresh_token,
          expires_at: account.expires_at, // Unix timestamp
        }
      }

      // Token is still valid
      if (Date.now() < (token.expires_at as number) * 1000) {
        return token
      }

      // Token expired, attempt refresh
      if (!token.refresh_token) {
        console.error("Missing refresh_token for token refresh")
        return { ...token, error: "RefreshAccessTokenError" }
      }

      try {
        const response = await fetch("https://meta.wikimedia.org/oauth2/access_token", {
          method: "POST",
          headers: {
            "Content-Type": "application/x-www-form-urlencoded",
          },
          body: new URLSearchParams({
            client_id: process.env.MEDIAWIKI_OAUTH_CLIENT_ID!,
            client_secret: process.env.MEDIAWIKI_OAUTH_CLIENT_SECRET!,
            grant_type: "refresh_token",
            refresh_token: token.refresh_token as string,
          }),
        })

        const refreshedTokens = await response.json()

        if (!response.ok) {
          console.error("Failed to refresh token:", refreshedTokens)
          return { ...token, error: "RefreshAccessTokenError" }
        }

        return {
          ...token,
          access_token: refreshedTokens.access_token,
          expires_at: Math.floor(Date.now() / 1000) + refreshedTokens.expires_in,
          refresh_token: refreshedTokens.refresh_token ?? token.refresh_token,
          error: undefined,
        }
      } catch (error) {
        console.error("Error refreshing access token:", error)
        return { ...token, error: "RefreshAccessTokenError" }
      }
    },
    async session({ session, token }) {
      session.accessToken = token.access_token as string
      session.error = token.error as string | undefined
      return session
    },
    async redirect({ url, baseUrl }) {
      if (url.startsWith("/")) return `${baseUrl}${url}`
      else if (new URL(url).origin === baseUrl) return url
      return baseUrl
    },
  },
} satisfies NextAuthConfig

export const { handlers, auth, signIn, signOut } = NextAuth(config)