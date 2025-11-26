import { Button } from '@/components/ui/Button'
import { Anchor } from '@/components/ui/Anchor'

interface TutorialFooterProps {
  evaluations: Map<string, boolean>
  requiredKeys: string[]
  onSubmit: () => void
}

export function TutorialFooter({ evaluations, requiredKeys, onSubmit }: TutorialFooterProps) {
  const isComplete = requiredKeys.every((key) => evaluations.has(key))

  return (
    <div className="flex justify-between items-center">
      <Anchor href="/evaluate" className="text-gray-500 hover:text-gray-700 font-medium">
        Skip Tutorial
      </Anchor>
      <Button onClick={onSubmit} disabled={!isComplete} className="px-6 py-3">
        Check Answers
      </Button>
    </div>
  )
}
