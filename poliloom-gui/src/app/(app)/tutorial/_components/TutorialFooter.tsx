import { PropertyActionItem } from '@/types'
import { Button } from '@/components/ui/Button'

interface TutorialFooterProps {
  actions: PropertyActionItem[]
  requiredKeys: string[]
  onSubmit: () => void
  onBack: () => void
  skipHref?: string
  onSkip?: () => void
}

export function TutorialFooter({
  actions,
  requiredKeys,
  onSubmit,
  onBack,
  skipHref,
  onSkip,
}: TutorialFooterProps) {
  const isComplete = requiredKeys.every((key) =>
    actions.some((a) => a.action !== 'create' && a.id === key),
  )

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
