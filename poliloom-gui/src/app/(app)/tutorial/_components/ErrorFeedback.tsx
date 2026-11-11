import { CenteredCard } from '@/components/ui/CenteredCard'
import { TutorialActions } from './TutorialActions'

interface ErrorFeedbackProps {
  title: string
  message: string
  hint: string
  onRetry: () => void
  onSkip: () => void
}

export function ErrorFeedback({ title, message, hint, onRetry, onSkip }: ErrorFeedbackProps) {
  return (
    <CenteredCard emoji="🤔" title={title}>
      <p className="mb-4">{message}</p>
      <p className="mb-8 text-accent-foreground font-medium">{hint}</p>
      <TutorialActions buttonText="Try Again" onNext={onRetry} onSkip={onSkip} />
    </CenteredCard>
  )
}
