import { Button } from '@/components/ui/Button'
import { useSkipTutorial } from './useSkipTutorial'

interface TutorialFooterProps {
  isComplete: boolean
  onSubmit: () => void
  onBack: () => void
  skipHref?: string
}

export function TutorialFooter({ isComplete, onSubmit, onBack, skipHref }: TutorialFooterProps) {
  const handleSkip = useSkipTutorial()

  return (
    <div className="flex justify-between items-center">
      <Button href={skipHref} variant="secondary" onClick={handleSkip} disabled={!skipHref}>
        Skip Tutorial
      </Button>
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
