interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

export function Spinner({ size = 'sm', className = '' }: SpinnerProps) {
  const sizeClasses = {
    sm: 'h-4 w-4 border-2',
    md: 'h-6 w-6 border-2',
    lg: 'h-8 w-8 border-3',
  }

  return (
    <div
      className={`animate-spin rounded-full border-b-indigo-600 border-t-transparent border-l-transparent border-r-transparent mr-2 ${sizeClasses[size]} ${className}`}
    />
  )
}
