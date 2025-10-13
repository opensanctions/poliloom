'use client'

import { Header } from '@/components/Header'

export default function GuidePage() {
  return (
    <>
      <Header />
      <main className="bg-gray-50 py-12 px-4 sm:px-6 lg:px-8 min-h-0 overflow-y-auto">
        <div className="max-w-4xl mx-auto">
          <div className="bg-white shadow rounded-lg">
            <div className="px-6 py-4 border-b border-gray-200">
              <h1 className="text-xl font-semibold text-gray-900">Guide</h1>
            </div>

            <div className="px-6 py-6">{/* Content will be added later */}</div>
          </div>
        </div>
      </main>
    </>
  )
}
