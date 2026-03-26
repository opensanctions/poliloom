import { Button } from '@/components/ui/Button'

interface TutorialFooterProps {
  isComplete: boolean
  onSubmit: () => void
  onBack: () => void
  skipHref?: string
  onSkip?: () => void
}

export function TutorialFooter({
  isComplete,
  onSubmit,
  onBack,
  skipHref,
  onSkip,
}: TutorialFooterProps) {
  return (
    <div className="flex justify-between items-center">
      <Button href={skipHref} variant="secondary" onClick={onSkip} disabled={!skipHref}>
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
