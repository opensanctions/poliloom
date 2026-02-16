'use client'

import { Button } from '@/components/ui/Button'
import { SpinningCounter } from '@/components/ui/SpinningCounter'
import { useEvaluationCount } from '@/contexts/EvaluationCountContext'

export function EvaluationCountButton() {
  const { evaluationCount } = useEvaluationCount()

  return (
    <Button
      href="/stats"
      variant="secondary"
      size="small"
      className="max-md:text-lg max-md:py-4 max-md:px-6 max-md:justify-start"
    >
      <SpinningCounter
        value={evaluationCount ?? 0}
        title="Total accepted and rejected statements"
      />
    </Button>
  )
}
