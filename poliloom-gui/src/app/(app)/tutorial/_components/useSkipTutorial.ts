import { useSettings } from '@/contexts/SettingsContext'

export function useSkipTutorial() {
  const { settings, patch } = useSettings()

  const handleSkip = () => {
    if (!settings?.basic_tutorial_completed) {
      patch({ basic_tutorial_completed: true })
    } else if (settings?.advanced_mode && !settings?.advanced_tutorial_completed) {
      patch({ advanced_tutorial_completed: true })
    }
  }

  return handleSkip
}
