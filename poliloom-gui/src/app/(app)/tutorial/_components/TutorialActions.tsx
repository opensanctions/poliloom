import { Button } from '@/components/ui/Button'

interface TutorialActionsProps {
  buttonText: string
  onNext: () => void
  skipHref?: string
  onSkip?: () => void
}

export function TutorialActions({ buttonText, onNext, skipHref, onSkip }: TutorialActionsProps) {
  return (
    <div className="flex flex-col gap-4">
      <Button onClick={onNext} size="large" fullWidth>
        {buttonText}
      </Button>
      <Button
        href={skipHref}
        variant="secondary"
        size="large"
        fullWidth
        onClick={onSkip}
        disabled={!skipHref}
      >
        Skip Tutorial
      </Button>
    </div>
  )
}
