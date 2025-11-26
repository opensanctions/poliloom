'use client'

import { useState, useEffect } from 'react'
import { Header } from '@/components/layout/Header'
import { TwoPanel } from '@/components/layout/TwoPanel'
import { Anchor } from '@/components/ui/Anchor'
import { CenteredCard } from '@/components/ui/CenteredCard'
import { PoliticianEvaluationView } from '@/components/evaluation/PoliticianEvaluationView'
import { PoliticianHeader } from '@/components/evaluation/PoliticianHeader'
import { ArchivedPageViewer } from '@/components/evaluation/ArchivedPageViewer'
import { PropertiesEvaluation } from '@/components/evaluation/PropertiesEvaluation'
import { TutorialActions } from './_components/TutorialActions'
import { TutorialFooter } from './_components/TutorialFooter'
import { SuccessFeedback } from './_components/SuccessFeedback'
import { ErrorFeedback } from './_components/ErrorFeedback'
import { useTutorial } from '@/contexts/TutorialContext'
import { Politician } from '@/types'
import tutorialData from './tutorialData.json'

const extractedDataPolitician = tutorialData.steps.extractedData.politician as Politician
const birthDatePolitician = tutorialData.steps.birthDateEvaluation.politician as Politician
const multipleSourcesPolitician = tutorialData.steps.multipleSources.politician as Politician
const genericVsSpecificPolitician = tutorialData.steps.genericVsSpecific.politician as Politician

// Expected answers for each evaluation step
type ExpectedEvaluations = Record<string, boolean>

const birthDateExpected: ExpectedEvaluations = {
  'tutorial-birth-date': true, // Accept - March 15, 1975 is correct
  'tutorial-birth-date-incorrect': false, // Reject - June 8, 1952 is the mother's birth date
}

const multipleSourcesExpected: ExpectedEvaluations = {
  'tutorial-position-1': true, // Accept - Member of Parliament
  'tutorial-position-2': true, // Accept - Minister of Education
}

const genericVsSpecificExpected: ExpectedEvaluations = {
  'tutorial-generic-position': false, // Reject - generic "Member of Parliament" when specific exists
}

interface EvaluationResult {
  isCorrect: boolean
  mistakes: string[]
}

function checkEvaluations(
  evaluations: Map<string, boolean>,
  expected: ExpectedEvaluations,
): EvaluationResult {
  const mistakes: string[] = []

  for (const [key, expectedValue] of Object.entries(expected)) {
    const actualValue = evaluations.get(key)
    if (actualValue !== expectedValue) {
      mistakes.push(key)
    }
  }

  return {
    isCorrect: mistakes.length === 0,
    mistakes,
  }
}

export default function TutorialPage() {
  const [step, setStep] = useState(0)
  const { completeTutorial } = useTutorial()

  // Track evaluation results for each interactive step
  const [birthDateResult, setBirthDateResult] = useState<EvaluationResult | null>(null)
  const [multipleSourcesResult, setMultipleSourcesResult] = useState<EvaluationResult | null>(null)
  const [genericVsSpecificResult, setGenericVsSpecificResult] = useState<EvaluationResult | null>(
    null,
  )

  // Keys to force remount of evaluation components on retry
  const [birthDateKey, setBirthDateKey] = useState(0)
  const [multipleSourcesKey, setMultipleSourcesKey] = useState(0)
  const [genericVsSpecificKey, setGenericVsSpecificKey] = useState(0)

  const nextStep = () => setStep(step + 1)

  // Mark tutorial as completed when reaching the final step
  useEffect(() => {
    if (step >= 13) {
      completeTutorial()
    }
  }, [step, completeTutorial])

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
          <div className="overflow-y-auto p-6 h-full">
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
          </div>
        }
        right={
          <CenteredCard emoji="🗂️" title="Extracted Data">
            <p>
              On the left, you&apos;ll see data automatically extracted from those source documents,
              alongside existing data already known.
            </p>
            <p className="mt-4">
              New items show the source text that was used as evidence for the extraction, and allow
              you to view the source document.
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
      <CenteredCard emoji="🎯" title="Give It a Try">
        <p className="mb-8">
          Compare the extracted data to the source. If they match, accept. If they don&apos;t,
          reject.
        </p>
        <TutorialActions buttonText="Let's do it" onNext={nextStep} />
      </CenteredCard>
    )
  } else if (step === 5) {
    // Interactive: birth date evaluation
    content = (
      <PoliticianEvaluationView
        key={`birth-date-${birthDateKey}`}
        politician={birthDatePolitician}
        header={<div className="text-sm text-indigo-600 font-medium mb-2">Tutorial Mode</div>}
        footer={(evaluations) => (
          <TutorialFooter
            evaluations={evaluations}
            expected={birthDateExpected}
            onSubmit={() => {
              const result = checkEvaluations(evaluations, birthDateExpected)
              setBirthDateResult(result)
              nextStep()
            }}
          />
        )}
        archivedPagesApiPath="/api/tutorial-pages"
      />
    )
  } else if (step === 6) {
    // Birth date result/feedback
    if (birthDateResult?.isCorrect) {
      content = (
        <SuccessFeedback
          title="Excellent!"
          message="You correctly identified that March 15, 1975 matches the source, while June 8, 1952 was actually the mother's birth date. Reading carefully makes all the difference!"
          onNext={nextStep}
        />
      )
    } else {
      content = (
        <ErrorFeedback
          title="Not Quite Right"
          message="Take another look at the source document. One birth date belongs to Jane Doe, and the other belongs to someone else mentioned in the text."
          hint="Hint: Look carefully at who each date refers to in the source text."
          onRetry={() => {
            setBirthDateKey((k) => k + 1)
            setBirthDateResult(null)
            setStep(5)
          }}
        />
      )
    }
  } else if (step === 7) {
    // Multiple sources explanation
    content = (
      <CenteredCard emoji="📚" title="Multiple Sources">
        <p className="mb-8">
          Sometimes information comes from different source documents. Next, try switching between
          these to evaluate all statements.
        </p>
        <TutorialActions buttonText="Let's do it" onNext={nextStep} />
      </CenteredCard>
    )
  } else if (step === 8) {
    // Interactive: positions evaluation
    content = (
      <PoliticianEvaluationView
        key={`multiple-sources-${multipleSourcesKey}`}
        politician={multipleSourcesPolitician}
        header={<div className="text-sm text-indigo-600 font-medium mb-2">Tutorial Mode</div>}
        footer={(evaluations) => (
          <TutorialFooter
            evaluations={evaluations}
            expected={multipleSourcesExpected}
            onSubmit={() => {
              const result = checkEvaluations(evaluations, multipleSourcesExpected)
              setMultipleSourcesResult(result)
              nextStep()
            }}
          />
        )}
        archivedPagesApiPath="/api/tutorial-pages"
      />
    )
  } else if (step === 9) {
    // Multiple sources result/feedback
    if (multipleSourcesResult?.isCorrect) {
      content = (
        <SuccessFeedback
          title="Great Job!"
          message="You correctly verified both positions from their respective source documents. Being able to work with multiple sources is an important skill!"
          onNext={nextStep}
        />
      )
    } else {
      content = (
        <ErrorFeedback
          title="Let's Try Again"
          message="Make sure to check each position against its source document. Click 'View' to switch between sources and verify each extraction."
          hint="Hint: Both positions are correctly extracted from their sources in this example."
          onRetry={() => {
            setMultipleSourcesKey((k) => k + 1)
            setMultipleSourcesResult(null)
            setStep(8)
          }}
        />
      )
    }
  } else if (step === 10) {
    // Generic vs specific explanation
    content = (
      <CenteredCard emoji="🎯" title="Specific Over Generic">
        <p className="mb-8">
          Specific data is better than generic data. If a more specific version already exists,
          reject the generic extraction.
        </p>
        <TutorialActions buttonText="Let's try it" onNext={nextStep} />
      </CenteredCard>
    )
  } else if (step === 11) {
    // Interactive: generic vs specific evaluation
    content = (
      <PoliticianEvaluationView
        key={`generic-vs-specific-${genericVsSpecificKey}`}
        politician={genericVsSpecificPolitician}
        header={<div className="text-sm text-indigo-600 font-medium mb-2">Tutorial Mode</div>}
        footer={(evaluations) => (
          <TutorialFooter
            evaluations={evaluations}
            expected={genericVsSpecificExpected}
            onSubmit={() => {
              const result = checkEvaluations(evaluations, genericVsSpecificExpected)
              setGenericVsSpecificResult(result)
              nextStep()
            }}
          />
        )}
        archivedPagesApiPath="/api/tutorial-pages"
      />
    )
  } else if (step === 12) {
    // Generic vs specific result/feedback
    if (genericVsSpecificResult?.isCorrect) {
      content = (
        <SuccessFeedback
          title="Perfect!"
          message="You correctly rejected the generic 'Member of Parliament' because the more specific 'Member of Springfield Parliament' already exists. Quality over quantity!"
          onNext={nextStep}
        />
      )
    } else {
      content = (
        <ErrorFeedback
          title="Almost There"
          message="Remember: when we already have specific data, we don't need a generic version. Look at what's already in Wikidata before accepting new extractions."
          hint="Hint: 'Member of Springfield Parliament' is more specific than 'Member of Parliament'."
          onRetry={() => {
            setGenericVsSpecificKey((k) => k + 1)
            setGenericVsSpecificResult(null)
            setStep(11)
          }}
        />
      )
    }
  } else {
    // Complete
    content = (
      <CenteredCard emoji="🎉" title="Tutorial Complete!">
        <p className="mb-8">
          You&apos;re all set! You now have everything you need to start verifying politician data.
        </p>
        <Anchor
          href="/evaluate"
          className="inline-flex items-center justify-center px-6 py-3 w-full bg-indigo-600 text-white font-medium hover:bg-indigo-700 rounded-md transition-colors"
        >
          Start Evaluating
        </Anchor>
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
