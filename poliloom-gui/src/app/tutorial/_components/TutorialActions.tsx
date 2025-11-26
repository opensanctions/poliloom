import { Button } from '@/components/ui/Button'
import { Anchor } from '@/components/ui/Anchor'

interface TutorialActionsProps {
  buttonText: string
  onNext: () => void
}

export function TutorialActions({ buttonText, onNext }: TutorialActionsProps) {
  return (
    <div className="flex flex-col gap-4">
      <Button onClick={onNext} className="px-6 py-3 w-full">
        {buttonText}
      </Button>
      <Anchor
        href="/evaluate"
        className="inline-flex items-center justify-center px-6 py-3 w-full text-gray-700 font-medium hover:bg-gray-100 rounded-md transition-colors"
      >
        Skip Tutorial
      </Anchor>
    </div>
  )
}
