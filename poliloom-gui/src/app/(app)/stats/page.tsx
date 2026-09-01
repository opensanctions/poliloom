import { getStats } from '@/lib/api-auth'
import { StatsContent } from './StatsContent'

export default async function StatsPage() {
  const stats = await getStats()
  return <StatsContent stats={stats} />
}
