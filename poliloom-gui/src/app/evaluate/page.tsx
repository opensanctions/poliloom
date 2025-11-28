'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Header } from '@/components/layout/Header'
import { PoliticianEvaluation } from '@/components/evaluation/PoliticianEvaluation'
import { useEvaluationSession } from '@/contexts/EvaluationSessionContext'
import { useTutorial } from '@/contexts/TutorialContext'
import { useUserPreferences } from '@/contexts/UserPreferencesContext'
import Link from 'next/link'

export default function EvaluatePage() {
  const router = useRouter()
  const { currentPolitician, loading, loadPoliticians, isSessionComplete } = useEvaluationSession()
  const { completeBasicTutorial, completeAdvancedTutorial } = useTutorial()
  const { isAdvancedMode } = useUserPreferences()

  // Mark tutorials complete once on mount
  useEffect(() => {
    completeBasicTutorial()
    if (isAdvancedMode) {
      completeAdvancedTutorial()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Navigate to completion page when session goal is reached
  useEffect(() => {
    if (isSessionComplete) {
      router.push('/evaluate/complete')
    }
  }, [isSessionComplete, router])

  return (
    <>
      <Header />

      {currentPolitician ? (
        <PoliticianEvaluation key={currentPolitician.id} politician={currentPolitician} />
      ) : (
        <main className="bg-gray-50 grid place-items-center py-12 px-4 sm:px-6 lg:px-8 min-h-0 overflow-y-auto">
          <div className="text-center max-w-2xl">
            {loading ? (
              <div className="text-gray-500">Loading politician data...</div>
            ) : (
              <div className="bg-gray-50 border border-gray-200 rounded-md p-4">
                <p className="text-gray-600">
                  Currently no politicians available, we&apos;re enriching more. You can wait a
                  minute, change your{' '}
                  <Link href="/" className="text-gray-700 hover:text-gray-900 underline">
                    filters
                  </Link>
                  , or{' '}
                  <button
                    onClick={loadPoliticians}
                    className="text-gray-700 hover:text-gray-900 underline cursor-pointer bg-transparent border-0 p-0 font-inherit"
                  >
                    reload
                  </button>
                  .
                </p>
              </div>
            )}
          </div>
        </main>
      )}
    </>
  )
}
