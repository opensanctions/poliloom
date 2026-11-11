import { Button } from '@/components/ui/Button'
import { useSkipTutorial } from './useSkipTutorial'

interface TutorialActionsProps {
  buttonText: string
  onNext: () => void
  onSkip: () => void
}

export function TutorialActions({ buttonText, onNext, onSkip }: TutorialActionsProps) {
  const handleSkip = useSkipTutorial()

  const skip = () => {
    handleSkip()
    onSkip()
  }

  return (
    <div className="flex flex-col gap-4">
      <Button onClick={onNext} size="large" fullWidth>
        {buttonText}
      </Button>
      <Button onClick={skip} variant="secondary" size="large" fullWidth>
        Skip Tutorial
      </Button>
    </div>
  )
}
