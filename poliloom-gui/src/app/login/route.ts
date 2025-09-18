import { signIn } from "@/auth"

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const callbackUrl = searchParams.get("callbackUrl") || "/"

  // Use NextAuth's signIn function to redirect to MediaWiki OAuth
  // This will throw a redirect response
  await signIn("wikimedia", { redirectTo: callbackUrl })
}