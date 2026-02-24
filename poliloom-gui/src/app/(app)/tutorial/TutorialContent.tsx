'use client'

import { useState, useEffect } from 'react'
import { TwoPanel } from '@/components/layout/TwoPanel'
import { Button } from '@/components/ui/Button'
import { CenteredCard } from '@/components/ui/CenteredCard'
import { PoliticianEvaluationView } from '@/components/evaluation/PoliticianEvaluationView'
import { PoliticianHeader } from '@/components/evaluation/PoliticianHeader'
import { ArchivedPageViewer } from '@/components/evaluation/ArchivedPageViewer'
import { PropertiesEvaluation } from '@/components/evaluation/PropertiesEvaluation'
import { TutorialActions } from './_components/TutorialActions'
import { TutorialFooter } from './_components/TutorialFooter'
import { SuccessFeedback } from './_components/SuccessFeedback'
import { ErrorFeedback } from './_components/ErrorFeedback'
import { useUserProgress } from '@/contexts/UserProgressContext'
import { useUserPreferences } from '@/contexts/UserPreferencesContext'
import { useEvaluationSession } from '@/contexts/EvaluationSessionContext'
import { useNextPoliticianContext } from '@/contexts/NextPoliticianContext'
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
  'tutorial-existing-specific-position': true, // Keep - don't deprecate the existing specific data
}
// Only new data keys are required for the submit button
const genericVsSpecificRequiredKeys: string[] = ['tutorial-generic-position']

// Advanced tutorial expected answers
const deprecateSimpleExpected: ExpectedEvaluations = {
  'tutorial-existing-generic-no-metadata': false, // Deprecate - generic with no metadata
  'tutorial-new-specific-position': true, // Accept - specific replacement
}
// Only new data keys are required for the submit button (existing data is optional to interact with)
const deprecateSimpleRequiredKeys: string[] = ['tutorial-new-specific-position']

const deprecateWithMetadataExpected: ExpectedEvaluations = {
  'tutorial-new-specific-with-source': true, // Accept the new specific data
  'tutorial-existing-with-metadata': true, // Keep - don't deprecate (metadata is valuable)
}
// Only new data keys are required for the submit button
const deprecateWithMetadataRequiredKeys: string[] = ['tutorial-new-specific-with-source']

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
    // For existing data (where expected is true = keep), only count as mistake if user deprecated it
    // If the key is not in evaluations, that means "keep" which is correct
    const actualValue = evaluations.get(key)
    if (expectedValue === true && actualValue === undefined) {
      // Expected to keep and user didn't touch it - correct, skip
      continue
    }
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
const BASIC_END = 13 // Last basic step
const ADVANCED_START = 14
const ADVANCED_END = 19 // Last advanced step

export interface TutorialContentProps {
  initialStep?: number // For testing - allows starting at any step
}

export function TutorialContent({ initialStep }: TutorialContentProps) {
  const {
    hasCompletedBasicTutorial,
    hasCompletedAdvancedTutorial,
    completeBasicTutorial,
    completeAdvancedTutorial,
  } = useUserProgress()
  const { isAdvancedMode } = useUserPreferences()
  const { startSession } = useEvaluationSession()
  const { nextHref } = useNextPoliticianContext()

  const startHref = nextHref || '/'

  // Determine starting step based on completion status
  const getStartingStep = (): number => {
    if (initialStep !== undefined) return initialStep
    if (!hasCompletedBasicTutorial) return BASIC_START
    if (isAdvancedMode && !hasCompletedAdvancedTutorial) return ADVANCED_START
    return BASIC_START
  }

  const [step, setStep] = useState(getStartingStep)

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

  // Completion screen
  if (isComplete) {
    return (
      <CenteredCard emoji="🎉" title="Tutorial Complete!">
        <p className="mb-8">
          You&apos;re all set! You now have everything you need to start verifying politician data.
        </p>
        <Button href={startHref} size="large" fullWidth onClick={() => startSession()}>
          Start Evaluating
        </Button>
      </CenteredCard>
    )
  }

  if (step === 0) {
    // Welcome
    return (
      <CenteredCard emoji="👋" title="Welcome to PoliLoom!">
        <p className="mb-8">
          You&apos;re about to help build accurate, open political data by verifying information
          extracted from official sources.
        </p>
        <TutorialActions
          skipHref={startHref}
          onSkip={() => startSession()}
          buttonText="Let's Go"
          onNext={nextStep}
        />
      </CenteredCard>
    )
  }

  if (step === 1) {
    // Why your help matters
    return (
      <CenteredCard emoji="🤖" title="Why Your Help Matters">
        <p className="mb-8">
          Your role is to check whether what the AI extracted actually matches what&apos;s written
          in the source document.
        </p>
        <TutorialActions
          skipHref={startHref}
          onSkip={() => startSession()}
          buttonText="Got It"
          onNext={nextStep}
        />
      </CenteredCard>
    )
  }

  if (step === 2) {
    // Show archived page (explanation left, iframe right)
    return (
      <TwoPanel
        left={
          <CenteredCard emoji="📄" title="Source Documents">
            <div className="mb-8 space-y-4">
              <p>
                On the right side, you&apos;ll see archived web pages from government portals,
                Wikipedia, and other official sources.
              </p>
              <p>
                These are the original documents where we found information about politicians. We
                save copies so you can verify the data even if the original page changes.
              </p>
            </div>
            <TutorialActions
              skipHref={startHref}
              onSkip={() => startSession()}
              buttonText="Next"
              onNext={nextStep}
            />
          </CenteredCard>
        }
        right={<ArchivedPageViewer pageId="tutorial-page-1" apiBasePath="/api/tutorial-pages" />}
      />
    )
  }

  if (step === 3) {
    // Show extracted data (properties left, explanation right)
    return (
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
            <div className="mb-8 space-y-4">
              <p>
                On the left, you&apos;ll see data automatically extracted from those source
                documents, alongside existing data already known.
              </p>
              <p>
                New items show the source text that was used as evidence for the extraction, and
                allow you to view the source document.
              </p>
            </div>
            <TutorialActions
              skipHref={startHref}
              onSkip={() => startSession()}
              buttonText="Next"
              onNext={nextStep}
            />
          </CenteredCard>
        }
      />
    )
  }

  if (step === 4) {
    // Let's try it
    return (
      <CenteredCard emoji="🎯" title="Give It a Try">
        <p className="mb-8">
          Compare the extracted data to the source. If they match, accept. If they don&apos;t,
          reject.
        </p>
        <TutorialActions
          skipHref={startHref}
          onSkip={() => startSession()}
          buttonText="Let's do it"
          onNext={nextStep}
        />
      </CenteredCard>
    )
  }

  if (step === 5) {
    // Interactive: birth date evaluation
    return (
      <PoliticianEvaluationView
        key={`birth-date-${birthDateKey}`}
        politician={birthDatePolitician}
        footer={(evaluations) => (
          <TutorialFooter
            skipHref={startHref}
            onSkip={() => startSession()}
            evaluations={evaluations}
            requiredKeys={Object.keys(birthDateExpected)}
            onSubmit={() => {
              const result = checkEvaluations(evaluations, birthDateExpected)
              setBirthDateResult(result)
              nextStep()
            }}
            onBack={() => setStep(4)}
          />
        )}
        archivedPagesApiPath="/api/tutorial-pages"
      />
    )
  }

  if (step === 6) {
    // Birth date result/feedback
    if (birthDateResult?.isCorrect) {
      return (
        <SuccessFeedback
          title="Excellent!"
          message="You correctly identified that March 15, 1975 matches the source, while June 8, 1952 was actually the mother's birth date. Reading carefully makes all the difference!"
          onNext={nextStep}
        />
      )
    }
    return (
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

  if (step === 7) {
    // Multiple sources explanation
    return (
      <CenteredCard emoji="📚" title="Multiple Sources">
        <p className="mb-8">
          Sometimes information comes from different source documents. Next, try switching between
          these to evaluate all statements.
        </p>
        <TutorialActions
          skipHref={startHref}
          onSkip={() => startSession()}
          buttonText="Let's do it"
          onNext={nextStep}
        />
      </CenteredCard>
    )
  }

  if (step === 8) {
    // Interactive: positions evaluation
    return (
      <PoliticianEvaluationView
        key={`multiple-sources-${multipleSourcesKey}`}
        politician={multipleSourcesPolitician}
        footer={(evaluations) => (
          <TutorialFooter
            skipHref={startHref}
            onSkip={() => startSession()}
            evaluations={evaluations}
            requiredKeys={Object.keys(multipleSourcesExpected)}
            onSubmit={() => {
              const result = checkEvaluations(evaluations, multipleSourcesExpected)
              setMultipleSourcesResult(result)
              nextStep()
            }}
            onBack={() => setStep(7)}
          />
        )}
        archivedPagesApiPath="/api/tutorial-pages"
      />
    )
  }

  if (step === 9) {
    // Multiple sources result/feedback
    if (multipleSourcesResult?.isCorrect) {
      return (
        <SuccessFeedback
          title="Great Job!"
          message="You correctly verified both positions from their respective source documents. Being able to work with multiple sources is an important skill!"
          onNext={nextStep}
        />
      )
    }
    return (
      <ErrorFeedback
        title="Let's Try Again"
        message={`Make sure to check each position against its source document. Click "View" to switch between sources and verify each extraction.`}
        hint="Hint: Both positions are correctly extracted from their sources in this example."
        onRetry={() => {
          setMultipleSourcesKey((k) => k + 1)
          setMultipleSourcesResult(null)
          setStep(8)
        }}
      />
    )
  }

  if (step === 10) {
    // Generic vs specific explanation
    return (
      <CenteredCard emoji="🎯" title="Specific Over Generic">
        <p className="mb-8">
          Specific data is better than generic data. If a more specific version already exists,
          reject the generic extraction.
        </p>
        <TutorialActions
          skipHref={startHref}
          onSkip={() => startSession()}
          buttonText="Let's do it"
          onNext={nextStep}
        />
      </CenteredCard>
    )
  }

  if (step === 11) {
    // Interactive: generic vs specific evaluation
    return (
      <PoliticianEvaluationView
        key={`generic-vs-specific-${genericVsSpecificKey}`}
        politician={genericVsSpecificPolitician}
        footer={(evaluations) => (
          <TutorialFooter
            skipHref={startHref}
            onSkip={() => startSession()}
            evaluations={evaluations}
            requiredKeys={genericVsSpecificRequiredKeys}
            onSubmit={() => {
              const result = checkEvaluations(evaluations, genericVsSpecificExpected)
              setGenericVsSpecificResult(result)
              nextStep()
            }}
            onBack={() => setStep(10)}
          />
        )}
        archivedPagesApiPath="/api/tutorial-pages"
      />
    )
  }

  if (step === 12) {
    // Generic vs specific result/feedback
    if (genericVsSpecificResult?.isCorrect) {
      return (
        <SuccessFeedback
          title="Perfect!"
          message={`You correctly rejected the generic "Member of Parliament" because the more specific "Member of Springfield Parliament" already exists. Quality over quantity!`}
          onNext={nextStep}
        />
      )
    }
    return (
      <ErrorFeedback
        title="Almost There"
        message="Remember: when we already have specific data, we don't need a generic version. Look at what data already exists before accepting new extractions."
        hint={`Hint: "Member of Springfield Parliament" is more specific than "Member of Parliament".`}
        onRetry={() => {
          setGenericVsSpecificKey((k) => k + 1)
          setGenericVsSpecificResult(null)
          setStep(11)
        }}
      />
    )
  }

  if (step === 13) {
    // Basic tutorial key takeaways
    return (
      <CenteredCard emoji="💡" title="Key Takeaways">
        <div className="mb-8 space-y-4">
          <p>
            Accept data that matches the source. Reject data that doesn&apos;t match or is less
            specific than what we already have.
          </p>
          <p>
            Not sure about something? That&apos;s completely fine — just skip it. You&apos;re never
            required to decide on every item.
          </p>
        </div>
        <TutorialActions
          skipHref={startHref}
          onSkip={() => startSession()}
          buttonText="Got It!"
          onNext={nextStep}
        />
      </CenteredCard>
    )
  }

  // ============ ADVANCED TUTORIAL STEPS (14-19) ============
  if (step === 14) {
    // Advanced mode welcome
    return (
      <CenteredCard emoji="⚡" title="Advanced Mode Tutorial">
        <div className="mb-8 space-y-4">
          <p>Welcome to advanced mode! You now have the power to deprecate existing data.</p>
          <p>
            This is useful when you find more specific or accurate data that should replace
            what&apos;s currently in Wikidata.
          </p>
        </div>
        <TutorialActions
          skipHref={startHref}
          onSkip={() => startSession()}
          buttonText="Let's Advance"
          onNext={nextStep}
        />
      </CenteredCard>
    )
  }

  if (step === 15) {
    // Chapter 1: Deprecating simple existing data
    return (
      <CenteredCard emoji="🔄" title="Replacing Generic Data">
        <div className="mb-8 space-y-4">
          <p>
            Sometimes existing data is to generic and could be replaced with something more
            specific.
          </p>
          <p>
            In these cases, you can deprecate the existing data and accept the more specific
            extraction.
          </p>
        </div>
        <TutorialActions
          skipHref={startHref}
          onSkip={() => startSession()}
          buttonText="Let's do it"
          onNext={nextStep}
        />
      </CenteredCard>
    )
  }

  if (step === 16) {
    // Interactive: deprecate simple existing data
    if (deprecateSimpleResult?.isCorrect) {
      return (
        <SuccessFeedback
          title="Well Done!"
          message={
            'You correctly deprecated the generic "Member of Parliament" and accepted the more specific "Member of Springfield Parliament". Nice work!'
          }
          onNext={nextStep}
        />
      )
    }
    if (deprecateSimpleResult) {
      return (
        <ErrorFeedback
          title="Not Quite Right"
          message={`The existing "Member of Parliament" is generic. The new extraction gives us more specific information - deprecate the old and accept the new.`}
          hint="Hint: Deprecate the generic existing data and accept the specific new extraction."
          onRetry={() => {
            setDeprecateSimpleKey((k) => k + 1)
            setDeprecateSimpleResult(null)
          }}
        />
      )
    }
    return (
      <PoliticianEvaluationView
        key={`deprecate-simple-${deprecateSimpleKey}`}
        politician={deprecateSimplePolitician}
        footer={(evaluations) => (
          <TutorialFooter
            skipHref={startHref}
            onSkip={() => startSession()}
            evaluations={evaluations}
            requiredKeys={deprecateSimpleRequiredKeys}
            onSubmit={() => {
              const result = checkEvaluations(evaluations, deprecateSimpleExpected)
              setDeprecateSimpleResult(result)
            }}
            onBack={() => setStep(15)}
          />
        )}
        archivedPagesApiPath="/api/tutorial-pages"
      />
    )
  }

  if (step === 17) {
    // Chapter 2: Deprecating data with qualifiers/references
    return (
      <CenteredCard emoji="⚠️" title="Data With Metadata">
        <div className="mb-8 space-y-4">
          <p>
            Some existing Wikidata statements have valuable metadata: references (sources) and
            qualifiers (like start/end dates).
          </p>
          <p>
            When you deprecate such data, this metadata is lost. Sometimes it&apos;s better to add
            your new data via PoliLoom, then manually edit Wikidata to preserve the metadata.
          </p>
        </div>
        <TutorialActions
          skipHref={startHref}
          onSkip={() => startSession()}
          buttonText="Let's do it"
          onNext={nextStep}
        />
      </CenteredCard>
    )
  }

  if (step === 18) {
    // Interactive: data with metadata - accept the new data AND keep the existing data
    if (deprecateWithMetadataResult?.isCorrect) {
      return (
        <SuccessFeedback
          title="Great Choice!"
          message="You accepted the new specific data and kept the existing data with its valuable metadata. Well done!"
          onNext={nextStep}
        />
      )
    }
    if (deprecateWithMetadataResult) {
      return (
        <ErrorFeedback
          title="Let's Reconsider"
          message="The new data is good, but the existing data has rich metadata attached. Deprecating it means losing all of that."
          hint="Hint: Accept the new extraction and keep the existing. Merge them manually in Wikidata later."
          onRetry={() => {
            setDeprecateWithMetadataKey((k) => k + 1)
            setDeprecateWithMetadataResult(null)
          }}
        />
      )
    }
    return (
      <PoliticianEvaluationView
        key={`deprecate-metadata-${deprecateWithMetadataKey}`}
        politician={deprecateWithMetadataPolitician}
        footer={(evaluations) => (
          <TutorialFooter
            skipHref={startHref}
            onSkip={() => startSession()}
            evaluations={evaluations}
            requiredKeys={deprecateWithMetadataRequiredKeys}
            onSubmit={() => {
              const result = checkEvaluations(evaluations, deprecateWithMetadataExpected)
              setDeprecateWithMetadataResult(result)
            }}
            onBack={() => setStep(17)}
          />
        )}
        archivedPagesApiPath="/api/tutorial-pages"
      />
    )
  }

  if (step === 19) {
    // Advanced tutorial summary
    return (
      <CenteredCard emoji="💡" title="Key Takeaways">
        <div className="mb-8 space-y-4">
          <p>
            Feel free to deprecate generic or incorrect existing data when you have better, more
            specific information.
          </p>
          <p>
            When existing data has references or qualifiers, consider whether that metadata is
            valuable. You might want to add your data first, then edit Wikidata manually to preserve
            the metadata.
          </p>
        </div>
        <TutorialActions
          skipHref={startHref}
          onSkip={() => startSession()}
          buttonText="Got It!"
          onNext={nextStep}
        />
      </CenteredCard>
    )
  }
}
