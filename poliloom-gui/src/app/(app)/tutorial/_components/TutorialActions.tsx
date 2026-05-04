import { Button } from '@/components/ui/Button'
import { useSkipTutorial } from './useSkipTutorial'

interface TutorialActionsProps {
  buttonText: string
  onNext: () => void
  skipHref?: string
}

export function TutorialActions({ buttonText, onNext, skipHref }: TutorialActionsProps) {
  const handleSkip = useSkipTutorial()

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
        onClick={handleSkip}
        disabled={!skipHref}
      >
        Skip Tutorial
      </Button>
    </div>
  )
}
