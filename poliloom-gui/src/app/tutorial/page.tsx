'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Header } from '@/components/Header'
import { Button } from '@/components/Button'
import { Anchor } from '@/components/Anchor'
import { CenteredCard } from '@/components/CenteredCard'
import { TutorialStep } from '@/components/TutorialStep'
import { useTutorial } from '@/contexts/TutorialContext'
import { Property, PropertyType, ArchivedPageResponse } from '@/types'
import tutorialData from './tutorialData.json'

// Build archived pages lookup
const archivedPages: Record<string, ArchivedPageResponse> = tutorialData.archivedPages as Record<
  string,
  ArchivedPageResponse
>

// Build properties with resolved archived pages
function getProperty(key: keyof typeof tutorialData.properties): Property {
  const propData = tutorialData.properties[key]
  return {
    ...propData,
    type: propData.type as PropertyType,
    archived_page: propData.archived_page_key
      ? archivedPages[propData.archived_page_key]
      : undefined,
  } as Property
}

const birthDateProperty = getProperty('birthDate')
const birthDateIncorrectProperty = getProperty('birthDateIncorrect')
const position1Property = getProperty('position1')
const position2Property = getProperty('position2')

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
    content = (
      <TutorialStep
        key={2}
        properties={[]}
        archivedPages={archivedPages}
        politician={tutorialData.politician}
        showArchivedPage={true}
        showLeftExplanation={true}
        showRightExplanation={false}
        isInteractive={false}
        explanationContent={
          <CenteredCard emoji="📄" title="Source Documents">
            <p>
              On the right side, you&apos;ll see archived web pages from government portals,
              Wikipedia, and other official sources.
            </p>
            <p className="mt-4">
              These are the original documents where we found information about politicians. We save
              copies so you can verify the data even if the original page changes.
            </p>
          </CenteredCard>
        }
        onNext={nextStep}
      />
    )
  } else if (step === 3) {
    content = (
      <TutorialStep
        key={3}
        properties={[birthDateProperty]}
        archivedPages={archivedPages}
        politician={tutorialData.politician}
        showArchivedPage={false}
        showLeftExplanation={false}
        showRightExplanation={true}
        isInteractive={false}
        explanationContent={
          <CenteredCard emoji="🗂️" title="Extracted Data">
            <p>
              On the left, you see structured data that was automatically extracted from the source
              documents using AI.
            </p>
          </CenteredCard>
        }
        onNext={nextStep}
      />
    )
  } else if (step === 4) {
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
    content = (
      <TutorialStep
        key={5}
        properties={[birthDateProperty, birthDateIncorrectProperty]}
        archivedPages={archivedPages}
        politician={tutorialData.politician}
        showArchivedPage={true}
        showLeftExplanation={false}
        showRightExplanation={false}
        isInteractive={true}
        explanationContent={
          <CenteredCard emoji="✨" title="Try It Yourself">
            <p>Now it&apos;s your turn! Review the data and click Accept or Reject.</p>
          </CenteredCard>
        }
        onNext={nextStep}
      />
    )
  } else if (step === 6) {
    content = (
      <TutorialStep
        key={6}
        properties={[position1Property, position2Property]}
        archivedPages={archivedPages}
        politician={tutorialData.politician}
        showArchivedPage={false}
        showLeftExplanation={false}
        showRightExplanation={true}
        isInteractive={false}
        explanationContent={
          <CenteredCard emoji="📚" title="Multiple Sources">
            <p>Sometimes information comes from different source documents.</p>
            <p className="mt-4">
              Click the &quot;View&quot; button next to any data item to see its source document.
            </p>
          </CenteredCard>
        }
        onNext={nextStep}
      />
    )
  } else if (step === 7) {
    content = (
      <TutorialStep
        key={7}
        properties={[position1Property, position2Property]}
        archivedPages={archivedPages}
        politician={tutorialData.politician}
        showArchivedPage={true}
        showLeftExplanation={false}
        showRightExplanation={false}
        isInteractive={true}
        explanationContent={
          <CenteredCard emoji="🔄" title="Try Multiple Sources">
            <p>Review these positions from different sources.</p>
          </CenteredCard>
        }
        onNext={nextStep}
      />
    )
  } else {
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
