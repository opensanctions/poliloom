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
      if (account) {
        token.accessToken = account.access_token
      }
      return token
    },
    async session({ session, token }) {
      session.accessToken = token.accessToken as string
      return session
    },
    async redirect({ url, baseUrl }) {
      if (url.startsWith("/")) return `${baseUrl}${url}`
      else if (new URL(url).origin === baseUrl) return url
      return baseUrl
    },
  },
  pages: {
    signIn: "/auth/login",
  },
} satisfies NextAuthConfig

export const { handlers, auth, signIn, signOut } = NextAuth(config)