import { Button } from '@/components/ui/Button'
import { useSkipTutorial } from './useSkipTutorial'

interface TutorialFooterProps {
  isComplete: boolean
  onSubmit: () => void
  onBack: () => void
  onSkip: () => void
}

export function TutorialFooter({ isComplete, onSubmit, onBack, onSkip }: TutorialFooterProps) {
  const handleSkip = useSkipTutorial()

  const skip = () => {
    handleSkip()
    onSkip()
  }

  return (
    <div className="flex justify-between items-center">
      <Button variant="secondary" onClick={skip}>
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
