export function Spinner() {
  return (
    <div className="animate-spin rounded-full h-6 w-6 border-2 border-b-indigo-600 border-t-transparent border-l-transparent border-r-transparent" />
  )
}

interface LoaderProps {
  message?: string
}

export function Loader({ message }: LoaderProps) {
  return (
    <div className="flex flex-col items-center gap-3">
      <Spinner />
      {message && <p className="text-gray-500">{message}</p>}
    </div>
  )
}
