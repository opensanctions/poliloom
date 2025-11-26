import { CenteredCard } from '@/components/ui/CenteredCard'
import { TutorialActions } from './TutorialActions'

interface SuccessFeedbackProps {
  title: string
  message: string
  onNext: () => void
}

export function SuccessFeedback({ title, message, onNext }: SuccessFeedbackProps) {
  return (
    <CenteredCard emoji="🎉" title={title}>
      <p className="mb-8">{message}</p>
      <TutorialActions buttonText="Continue" onNext={onNext} />
    </CenteredCard>
  )
}
