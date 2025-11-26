import Link from 'next/link'

interface AnchorProps {
  href: string
  children: React.ReactNode
  className?: string
}

export function Anchor({ href, children, className }: AnchorProps) {
  // Use default nav link styling if no className provided
  const finalClassName =
    className || 'px-2 py-1 text-sm text-gray-600 hover:text-gray-800 transition-colors font-medium'

  // External link
  if (href.startsWith('http://') || href.startsWith('https://')) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" className={finalClassName}>
        {children}
      </a>
    )
  }

  // Internal link
  return (
    <Link href={href} className={finalClassName}>
      {children}
    </Link>
  )
}
