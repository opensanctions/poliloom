'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Header } from '@/components/Header'
import { Button } from '@/components/Button'
import { Anchor } from '@/components/Anchor'
import { CenteredCard } from '@/components/CenteredCard'
import { PoliticianEvaluation } from '@/components/PoliticianEvaluation'
import { PoliticianHeader } from '@/components/PoliticianHeader'
import { ArchivedPageViewer } from '@/components/ArchivedPageViewer'
import { PropertiesEvaluation } from '@/components/PropertiesEvaluation'
import { useTutorial } from '@/contexts/TutorialContext'
import { Politician } from '@/types'
import tutorialData from './tutorialData.json'

const extractedDataPolitician = tutorialData.steps.extractedData.politician as Politician
const birthDatePolitician = tutorialData.steps.birthDateEvaluation.politician as Politician
const multipleSourcesPolitician = tutorialData.steps.multipleSources.politician as Politician

function TutorialActions({ buttonText, onNext }: { buttonText: string; onNext: () => void }) {
  return (
    <div className="flex flex-col gap-4">
      <Button onClick={onNext} className="px-6 py-3 w-full">
        {buttonText}
      </Button>
      <Anchor
        href="/evaluate"
        className="inline-flex items-center justify-center px-6 py-3 w-full text-gray-700 font-medium hover:bg-gray-100 rounded-md transition-colors"
      >
        Skip Tutorial
      </Anchor>
    </div>
  )
}

function TutorialFooter({ onNext }: { onNext: () => void }) {
  return (
    <div className="flex justify-between items-center">
      <Anchor href="/evaluate" className="text-gray-500 hover:text-gray-700 font-medium">
        Skip Tutorial
      </Anchor>
      <Button onClick={onNext} className="px-6 py-3">
        Continue
      </Button>
    </div>
  )
}

function TwoPanel({ left, right }: { left: React.ReactNode; right: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[46rem_1fr] bg-gray-50 min-h-0">
      <div className="shadow-lg overflow-y-auto min-h-0 p-6">{left}</div>
      <div className="bg-gray-50 border-l border-gray-200 overflow-hidden min-h-0 flex items-center justify-center">
        {right}
      </div>
    </div>
  )
}

export default function TutorialPage() {
  const router = useRouter()
  const { completeTutorial } = useTutorial()
  const [step, setStep] = useState(0)

  const nextStep = () => setStep(step + 1)

  const handleComplete = () => {
    completeTutorial()
    router.push('/evaluate')
  }

  let content: React.ReactNode

  if (step === 0) {
    // Welcome
    content = (
      <CenteredCard emoji="👋" title="Welcome to PoliLoom!">
        <p className="mb-8">
          You&apos;re about to help build accurate, open political data by verifying information
          extracted from official sources.
        </p>
        <TutorialActions buttonText="Let's Go" onNext={nextStep} />
      </CenteredCard>
    )
  } else if (step === 1) {
    // Why your help matters
    content = (
      <CenteredCard emoji="🤖" title="Why Your Help Matters">
        <p className="mb-8">
          Your role is to check whether what the AI extracted actually matches what&apos;s written
          in the source document.
        </p>
        <TutorialActions buttonText="Got It" onNext={nextStep} />
      </CenteredCard>
    )
  } else if (step === 2) {
    // Show archived page (explanation left, iframe right)
    content = (
      <TwoPanel
        left={
          <CenteredCard emoji="📄" title="Source Documents">
            <p>
              On the right side, you&apos;ll see archived web pages from government portals,
              Wikipedia, and other official sources.
            </p>
            <p className="mt-4">
              These are the original documents where we found information about politicians. We save
              copies so you can verify the data even if the original page changes.
            </p>
            <div className="mt-8">
              <TutorialActions buttonText="Next" onNext={nextStep} />
            </div>
          </CenteredCard>
        }
        right={<ArchivedPageViewer pageId="tutorial-page-1" apiBasePath="/api/tutorial-pages" />}
      />
    )
  } else if (step === 3) {
    // Show extracted data (properties left, explanation right)
    content = (
      <TwoPanel
        left={
          <>
            <div className="mb-6">
              <div className="text-sm text-indigo-600 font-medium mb-2">Tutorial Mode</div>
              <PoliticianHeader
                name={extractedDataPolitician.name}
                wikidataId={extractedDataPolitician.wikidata_id ?? undefined}
              />
            </div>
            <PropertiesEvaluation
              properties={extractedDataPolitician.properties}
              evaluations={new Map()}
              onAction={() => {}}
              onShowArchived={() => {}}
              onHover={() => {}}
              activeArchivedPageId={null}
            />
          </>
        }
        right={
          <CenteredCard emoji="🗂️" title="Extracted Data">
            <p>
              On the left, you see data automatically extracted from source documents, alongside
              existing data already in Wikidata.
            </p>
            <div className="mt-8">
              <TutorialActions buttonText="Next" onNext={nextStep} />
            </div>
          </CenteredCard>
        }
      />
    )
  } else if (step === 4) {
    // Let's try it
    content = (
      <CenteredCard emoji="🎯" title="Let's Try It">
        <p className="mb-8">
          Compare the extracted data to the source. If they match, accept. If they don&apos;t,
          reject.
        </p>
        <TutorialActions buttonText="Got It" onNext={nextStep} />
      </CenteredCard>
    )
  } else if (step === 5) {
    // Interactive: birth date evaluation
    content = (
      <PoliticianEvaluation
        key="step-5"
        politician={birthDatePolitician}
        footer={<TutorialFooter onNext={nextStep} />}
        archivedPagesApiPath="/api/tutorial-pages"
      />
    )
  } else if (step === 6) {
    // Multiple sources explanation (properties left, explanation right)
    content = (
      <TwoPanel
        left={
          <>
            <div className="mb-6">
              <div className="text-sm text-indigo-600 font-medium mb-2">Tutorial Mode</div>
              <PoliticianHeader
                name={multipleSourcesPolitician.name}
                wikidataId={multipleSourcesPolitician.wikidata_id ?? undefined}
              />
            </div>
            <PropertiesEvaluation
              properties={multipleSourcesPolitician.properties}
              evaluations={new Map()}
              onAction={() => {}}
              onShowArchived={() => {}}
              onHover={() => {}}
              activeArchivedPageId={null}
            />
          </>
        }
        right={
          <CenteredCard emoji="📚" title="Multiple Sources">
            <p>Sometimes information comes from different source documents.</p>
            <p className="mt-4">
              Click the &quot;View&quot; button next to any data item to see its source document.
            </p>
            <div className="mt-8">
              <TutorialActions buttonText="Next" onNext={nextStep} />
            </div>
          </CenteredCard>
        }
      />
    )
  } else if (step === 7) {
    // Interactive: positions evaluation
    content = (
      <PoliticianEvaluation
        key="step-7"
        politician={multipleSourcesPolitician}
        footer={<TutorialFooter onNext={nextStep} />}
        archivedPagesApiPath="/api/tutorial-pages"
      />
    )
  } else {
    // Complete
    content = (
      <CenteredCard emoji="🎉" title="Tutorial Complete!">
        <div className="mb-8">
          <p>Great job! You now know how to:</p>
          <ul className="text-left mt-4 space-y-2">
            <li>• View source documents with highlighted text</li>
            <li>• Review extracted data and accept or reject it</li>
            <li>• Handle multiple sources for different data</li>
          </ul>
        </div>
        <Button onClick={handleComplete} className="px-6 py-3 w-full">
          Start Evaluating
        </Button>
      </CenteredCard>
    )
  }

  return (
    <>
      <Header />
      {content}
    </>
  )
}
