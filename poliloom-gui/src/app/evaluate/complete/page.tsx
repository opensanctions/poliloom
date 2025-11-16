'use client'

import { useRouter } from 'next/navigation'
import { useEvaluation } from '@/contexts/EvaluationContext'
import { Button } from '@/components/Button'
import { Header } from '@/components/Header'

export default function CompletePage() {
  const router = useRouter()
  const { sessionGoal, resetSession } = useEvaluation()

  const handleStartAnother = () => {
    resetSession()
    router.push('/evaluate')
  }

  const handleReturnHome = () => {
    resetSession()
    router.push('/')
  }

  return (
    <>
      <Header />
      <div className="flex items-center justify-center min-h-0 flex-1 bg-gray-50">
        <div className="text-center max-w-md p-8">
          <div className="text-6xl mb-6">🎉</div>
          <h1 className="text-3xl font-bold text-gray-900 mb-4">Session Complete!</h1>
          <p className="text-lg text-gray-600 mb-8">
            Great work! You&apos;ve reviewed {sessionGoal} politicians.
          </p>

          <div className="flex flex-col gap-4">
            <Button onClick={handleStartAnother} className="px-6 py-3 w-full">
              Start Another Round
            </Button>
            <Button onClick={handleReturnHome} variant="secondary" className="px-6 py-3 w-full">
              Return Home
            </Button>
          </div>
        </div>
      </div>
    </>
  )
}
