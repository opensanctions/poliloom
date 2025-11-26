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
import { useUserPreferences } from '@/contexts/UserPreferencesContext'
import { Politician } from '@/types'
import tutorialData from './tutorialData.json'

const extractedDataPolitician = tutorialData.steps.extractedData.politician as Politician
const birthDatePolitician = tutorialData.steps.birthDateEvaluation.politician as Politician
const multipleSourcesPolitician = tutorialData.steps.multipleSources.politician as Politician
const genericVsSpecificPolitician = tutorialData.steps.genericVsSpecific.politician as Politician
const deprecateSimplePolitician = tutorialData.steps.deprecateSimple.politician as Politician
const deprecateWithMetadataPolitician = tutorialData.steps.deprecateWithMetadata
  .politician as Politician

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

// Advanced tutorial expected answers
const deprecateSimpleExpected: ExpectedEvaluations = {
  'tutorial-existing-generic-no-metadata': false, // Deprecate - generic with no metadata
  'tutorial-new-specific-position': true, // Accept - specific replacement
}

const deprecateWithMetadataExpected: ExpectedEvaluations = {
  'tutorial-new-specific-with-source': true, // Accept the new specific data
  // Note: We DON'T require deprecating the existing data - the lesson is to be careful
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

// Step ranges
const BASIC_START = 0
const BASIC_END = 12 // Last basic step
const ADVANCED_START = 13
const ADVANCED_END = 18 // Last advanced step

export default function TutorialPage() {
  const {
    hasCompletedBasicTutorial,
    hasCompletedAdvancedTutorial,
    completeBasicTutorial,
    completeAdvancedTutorial,
  } = useTutorial()
  const { isAdvancedMode } = useUserPreferences()

  // Determine starting step based on completion status
  const startingStep = (): number => {
    if (!hasCompletedBasicTutorial) return BASIC_START
    if (isAdvancedMode && !hasCompletedAdvancedTutorial) return ADVANCED_START
    return BASIC_START
  }

  const [step, setStep] = useState(startingStep)

  // Track evaluation results for each interactive step
  const [birthDateResult, setBirthDateResult] = useState<EvaluationResult | null>(null)
  const [multipleSourcesResult, setMultipleSourcesResult] = useState<EvaluationResult | null>(null)
  const [genericVsSpecificResult, setGenericVsSpecificResult] = useState<EvaluationResult | null>(
    null,
  )
  // Advanced tutorial results
  const [deprecateSimpleResult, setDeprecateSimpleResult] = useState<EvaluationResult | null>(null)
  const [deprecateWithMetadataResult, setDeprecateWithMetadataResult] =
    useState<EvaluationResult | null>(null)

  // Keys to force remount of evaluation components on retry
  const [birthDateKey, setBirthDateKey] = useState(0)
  const [multipleSourcesKey, setMultipleSourcesKey] = useState(0)
  const [genericVsSpecificKey, setGenericVsSpecificKey] = useState(0)
  const [deprecateSimpleKey, setDeprecateSimpleKey] = useState(0)
  const [deprecateWithMetadataKey, setDeprecateWithMetadataKey] = useState(0)

  const nextStep = () => setStep(step + 1)

  // Handle tutorial completion
  useEffect(() => {
    // Complete basic tutorial when passing the last basic step
    if (step > BASIC_END && !hasCompletedBasicTutorial) {
      completeBasicTutorial()
    }
    // Complete advanced tutorial when passing the last advanced step
    if (step > ADVANCED_END) {
      completeAdvancedTutorial()
    }
  }, [step, hasCompletedBasicTutorial, completeBasicTutorial, completeAdvancedTutorial])

  // Determine what to show
  const isBasicComplete = step > BASIC_END
  const isAdvancedComplete = step > ADVANCED_END
  const shouldShowAdvanced = isAdvancedMode && !hasCompletedAdvancedTutorial

  // Show completion screen when:
  // - Basic is done AND (not in advanced mode OR advanced is already completed)
  // - OR advanced is done
  const isComplete = (isBasicComplete && !shouldShowAdvanced) || isAdvancedComplete

  let content: React.ReactNode

  // Completion screen
  if (isComplete) {
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
  } else if (step === 0) {
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
        footer={(evaluations) => (
          <TutorialFooter
            evaluations={evaluations}
            requiredKeys={Object.keys(birthDateExpected)}
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
        footer={(evaluations) => (
          <TutorialFooter
            evaluations={evaluations}
            requiredKeys={Object.keys(multipleSourcesExpected)}
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
        footer={(evaluations) => (
          <TutorialFooter
            evaluations={evaluations}
            requiredKeys={Object.keys(genericVsSpecificExpected)}
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
  }
  // ============ ADVANCED TUTORIAL STEPS (13-18) ============
  else if (step === 13) {
    // Advanced mode welcome
    content = (
      <CenteredCard emoji="⚡" title="Advanced Mode Tutorial">
        <p className="mb-4">
          Welcome to advanced mode! You now have the power to deprecate existing Wikidata
          statements.
        </p>
        <p className="mb-8">
          This is useful when you find more specific or accurate data that should replace
          what&apos;s currently in Wikidata.
        </p>
        <TutorialActions buttonText="Let's Learn" onNext={nextStep} />
      </CenteredCard>
    )
  } else if (step === 14) {
    // Chapter 1: Deprecating simple existing data
    content = (
      <CenteredCard emoji="🔄" title="Replacing Generic Data">
        <p className="mb-4">
          Sometimes Wikidata has generic data that should be replaced with something more specific.
        </p>
        <p className="mb-8">
          In these cases, you can deprecate the existing data and accept the more specific
          extraction. Let&apos;s try an example.
        </p>
        <TutorialActions buttonText="Show Me" onNext={nextStep} />
      </CenteredCard>
    )
  } else if (step === 15) {
    // Interactive: deprecate simple existing data
    if (deprecateSimpleResult?.isCorrect) {
      content = (
        <SuccessFeedback
          title="Well Done!"
          message="You correctly deprecated the generic 'Member of Parliament' and accepted the more specific 'Member of Springfield Parliament'. Nice work!"
          onNext={nextStep}
        />
      )
    } else if (deprecateSimpleResult) {
      content = (
        <ErrorFeedback
          title="Not Quite Right"
          message="The existing 'Member of Parliament' is generic. The new extraction gives us more specific information - deprecate the old and accept the new."
          hint="Hint: Deprecate the generic existing data and accept the specific new extraction."
          onRetry={() => {
            setDeprecateSimpleKey((k) => k + 1)
            setDeprecateSimpleResult(null)
          }}
        />
      )
    } else {
      content = (
        <PoliticianEvaluationView
          key={`deprecate-simple-${deprecateSimpleKey}`}
          politician={deprecateSimplePolitician}
          footer={(evaluations) => (
            <TutorialFooter
              evaluations={evaluations}
              requiredKeys={Object.keys(deprecateSimpleExpected)}
              onSubmit={() => {
                const result = checkEvaluations(evaluations, deprecateSimpleExpected)
                setDeprecateSimpleResult(result)
              }}
            />
          )}
          archivedPagesApiPath="/api/tutorial-pages"
        />
      )
    }
  } else if (step === 16) {
    // Chapter 2: Deprecating data with qualifiers/references
    content = (
      <CenteredCard emoji="⚠️" title="Data With Metadata">
        <p className="mb-4">
          Some existing Wikidata statements have valuable metadata: references (sources) and
          qualifiers (like start/end dates).
        </p>
        <p className="mb-4">
          When you deprecate such data, this metadata is lost. Sometimes it&apos;s better to add
          your new data via PoliLoom, then manually edit Wikidata to preserve the metadata.
        </p>
        <p className="mb-8">Let&apos;s see an example where you might want to be more careful.</p>
        <TutorialActions buttonText="Show Me" onNext={nextStep} />
      </CenteredCard>
    )
  } else if (step === 17) {
    // Interactive: data with metadata - just need to accept the new data
    if (deprecateWithMetadataResult?.isCorrect) {
      content = (
        <SuccessFeedback
          title="Great Choice!"
          message="You accepted the new specific data. Notice the existing data has references and qualifiers - valuable metadata that would be lost if deprecated. In cases like this, you might want to add the new data through PoliLoom first, then manually edit Wikidata to merge or update the existing statement."
          onNext={nextStep}
        />
      )
    } else if (deprecateWithMetadataResult) {
      content = (
        <ErrorFeedback
          title="Let's Reconsider"
          message="Look at the existing data - it has references (sources) and qualifiers (dates). This metadata is valuable and would be lost if you deprecate it."
          hint="Hint: Accept the new specific extraction. You can choose whether to deprecate the existing data, but consider that its metadata has value."
          onRetry={() => {
            setDeprecateWithMetadataKey((k) => k + 1)
            setDeprecateWithMetadataResult(null)
          }}
        />
      )
    } else {
      content = (
        <PoliticianEvaluationView
          key={`deprecate-metadata-${deprecateWithMetadataKey}`}
          politician={deprecateWithMetadataPolitician}
          footer={(evaluations) => (
            <TutorialFooter
              evaluations={evaluations}
              requiredKeys={Object.keys(deprecateWithMetadataExpected)}
              onSubmit={() => {
                const result = checkEvaluations(evaluations, deprecateWithMetadataExpected)
                setDeprecateWithMetadataResult(result)
              }}
            />
          )}
          archivedPagesApiPath="/api/tutorial-pages"
        />
      )
    }
  } else if (step === 18) {
    // Advanced tutorial summary
    content = (
      <CenteredCard emoji="💡" title="Key Takeaways">
        <div className="mb-8 space-y-4">
          <p>
            <strong>Simple cases:</strong> Feel free to deprecate generic or incorrect existing data
            when you have better, more specific information.
          </p>
          <p>
            <strong>Data with metadata:</strong> When existing data has references or qualifiers,
            consider whether that metadata is valuable. You might want to add your data first, then
            edit Wikidata manually to preserve the metadata.
          </p>
        </div>
        <TutorialActions buttonText="Got It!" onNext={nextStep} />
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
