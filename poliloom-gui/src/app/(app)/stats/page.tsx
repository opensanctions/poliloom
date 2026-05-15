import { Button } from '@/components/ui/Button'
import { CenteredCard } from '@/components/ui/CenteredCard'
import { getSettings, getStats } from '@/lib/api-auth'
import { StatsContent } from './StatsContent'

export default async function StatsPage() {
  const settings = await getSettings()

  if (!settings.stats_unlocked) {
    return (
      <CenteredCard emoji="🔒" title="Stats Locked">
        <p className="mb-8">
          Complete your first evaluation session to unlock the community stats.
        </p>
        <Button href="/" size="large" fullWidth>
          Start Evaluating
        </Button>
      </CenteredCard>
    )
  }

  const stats = await getStats()
  return <StatsContent stats={stats} />
}
