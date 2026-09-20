'use client'

import { Button } from '@/components/ui/Button'
import { SpinningCounter } from '@/components/ui/SpinningCounter'
import { useDecisionCount } from '@/contexts/DecisionCountContext'

export function EvaluationCountButton() {
  const { decisionCount } = useDecisionCount()

  return (
    <Button
      href="/stats"
      variant="secondary"
      size="small"
      className="max-md:text-lg max-md:py-4 max-md:px-6 max-md:justify-start"
    >
      <SpinningCounter value={decisionCount ?? 0} title="Total accepted and rejected statements" />
    </Button>
  )
}
