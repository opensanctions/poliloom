import { Button } from '@/components/ui/Button'

interface TutorialActionsProps {
  buttonText: string
  onNext: () => void
}

export function TutorialActions({ buttonText, onNext }: TutorialActionsProps) {
  return (
    <div className="flex flex-col gap-4">
      <Button onClick={onNext} size="large" fullWidth>
        {buttonText}
      </Button>
      <Button href="/evaluate" variant="secondary" size="large" fullWidth>
        Skip Tutorial
      </Button>
    </div>
  )
}
