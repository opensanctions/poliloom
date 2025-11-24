'use client'

import { Header } from '@/components/Header'
import { PoliticianEvaluation } from '@/components/PoliticianEvaluation'
import { useEvaluation } from '@/contexts/EvaluationContext'
import Link from 'next/link'

export default function EvaluatePage() {
  const { currentPolitician, loading, loadPoliticians } = useEvaluation()

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
