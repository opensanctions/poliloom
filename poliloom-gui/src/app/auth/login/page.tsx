import { signIn } from "@/auth"

export default function LoginPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
            PoliLoom Data Confirmation
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600">
            Sign in with your MediaWiki account to confirm politician data
          </p>
        </div>
        <form
          action={async () => {
            "use server"
            await signIn("wikimedia")
          }}
        >
          <button
            type="submit"
            className="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
          >
            Sign in with MediaWiki
          </button>
        </form>
      </div>
    </div>
  )
}