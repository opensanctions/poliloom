import { Button } from '@/components/ui/Button'
import { CenteredCard } from '@/components/ui/CenteredCard'
import { fetchWithAuth, getUser } from '@/lib/api-auth'
import { StatsResponse } from '@/types'
import { StatsContent } from './StatsContent'

async function getStats(): Promise<StatsResponse | null> {
  const res = await fetchWithAuth(`${process.env.API_BASE_URL}/stats`, { cache: 'no-store' })
  if (!res?.ok) return null
  return res.json()
}

export default async function StatsPage() {
  const user = await getUser()
  const statsUnlocked = user?.settings.stats_unlocked ?? false

  if (!statsUnlocked) {
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
