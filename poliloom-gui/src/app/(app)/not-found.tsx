'use client'

import { usePathname } from 'next/navigation'
import { CenteredCard } from '@/components/ui/CenteredCard'
import { Button } from '@/components/ui/Button'

function ExternalLinkIcon() {
  return (
    <svg className="inline w-4 h-4 ml-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
      />
    </svg>
  )
}

export default function NotFound() {
  const pathname = usePathname()
  const match = pathname.match(/^\/politician\/(Q\d+)$/)
  const qid = match?.[1]

  return (
    <CenteredCard emoji="🔍" title="Not Found">
      <p className="mb-8">
        This person isn&apos;t in PoliLoom. We import humans with{' '}
        <a
          href="https://www.wikidata.org/wiki/Property:P106"
          target="_blank"
          rel="noopener noreferrer"
          className="text-accent-foreground hover:text-accent-foreground-hover"
        >
          occupation
          <ExternalLinkIcon />
        </a>{' '}
        <a
          href="https://www.wikidata.org/wiki/Q82955"
          target="_blank"
          rel="noopener noreferrer"
          className="text-accent-foreground hover:text-accent-foreground-hover"
        >
          politician
          <ExternalLinkIcon />
        </a>{' '}
        or a{' '}
        <a
          href="https://www.wikidata.org/wiki/Property:P39"
          target="_blank"
          rel="noopener noreferrer"
          className="text-accent-foreground hover:text-accent-foreground-hover"
        >
          position held
          <ExternalLinkIcon />
        </a>{' '}
        we track. If you can add one of these on Wikidata, they&apos;ll appear here on the next
        import.
      </p>
      <div className="flex flex-col gap-4">
        {qid && (
          <Button href={`https://www.wikidata.org/wiki/${qid}`} size="large" fullWidth>
            View on Wikidata
          </Button>
        )}
        <Button href="/" variant="secondary" size="large" fullWidth>
          Return Home
        </Button>
      </div>
    </CenteredCard>
  )
}
