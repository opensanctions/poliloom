import { useSettings } from '@/contexts/SettingsContext'
import { useEvaluationSession } from '@/contexts/EvaluationSessionContext'

export function useSkipTutorial() {
  const { settings, patch } = useSettings()
  const { startSession } = useEvaluationSession()

  const handleSkip = () => {
    if (!settings?.basic_tutorial_completed) {
      patch({ basic_tutorial_completed: true })
    } else if (settings?.advanced_mode && !settings?.advanced_tutorial_completed) {
      patch({ advanced_tutorial_completed: true })
    }
    startSession()
  }

  return handleSkip
}
