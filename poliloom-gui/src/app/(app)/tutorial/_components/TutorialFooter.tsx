import Link from 'next/link'
import { Button } from '@/components/ui/Button'

interface TutorialFooterProps {
  evaluations: Map<string, boolean>
  requiredKeys: string[]
  onSubmit: () => void
  onBack: () => void
  skipHref: string
  onSkip?: () => void
}

export function TutorialFooter({
  evaluations,
  requiredKeys,
  onSubmit,
  onBack,
  skipHref,
  onSkip,
}: TutorialFooterProps) {
  const isComplete = requiredKeys.every((key) => evaluations.has(key))

  return (
    <div className="flex justify-between items-center">
      <Link
        href={skipHref}
        onClick={onSkip}
        className="text-foreground-tertiary hover:text-foreground-secondary font-medium"
      >
        Skip Tutorial
      </Link>
      <div className="flex gap-3">
        <Button onClick={onBack} variant="secondary" size="large">
          Go Back
        </Button>
        <Button onClick={onSubmit} disabled={!isComplete} size="large">
          Check Answers
        </Button>
      </div>
    </div>
  )
}
