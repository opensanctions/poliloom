export function Spinner() {
  return (
    <div className="h-6 w-6 animate-spin rounded-full border-2 border-b-accent border-t-transparent border-l-transparent border-r-transparent" />
  )
}

interface LoaderProps {
  message?: string
}

export function Loader({ message }: LoaderProps) {
  return (
    <div className="flex flex-col items-center gap-3">
      <Spinner />
      {message && <p className="text-foreground-muted">{message}</p>}
    </div>
  )
}
