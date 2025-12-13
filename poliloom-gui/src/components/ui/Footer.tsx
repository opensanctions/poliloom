import { Button } from './Button'

export function Footer() {
  return (
    <div className="flex justify-center gap-3 py-8">
      <Button href="https://www.opensanctions.org/impressum/" variant="secondary" size="small">
        Impressum
      </Button>
      {process.env.NEXT_PUBLIC_WIKIDATA_CONTRIBUTIONS_URL && (
        <Button
          href={process.env.NEXT_PUBLIC_WIKIDATA_CONTRIBUTIONS_URL}
          variant="secondary"
          size="small"
          className="text-indigo-600 hover:text-indigo-700"
        >
          View Wikidata contributions
          <svg className="w-4 h-4 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
            />
          </svg>
        </Button>
      )}
    </div>
  )
}
