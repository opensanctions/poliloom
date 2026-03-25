'use client'

import { useState, useEffect } from 'react'
import { TwoPanel } from '@/components/layout/TwoPanel'
import { Button } from '@/components/ui/Button'
import { CenteredCard } from '@/components/ui/CenteredCard'
import { EvaluationView } from '@/components/evaluation/EvaluationView'
import { PoliticianHeader } from '@/components/evaluation/PoliticianHeader'
import { SourceViewer } from '@/components/evaluation/SourceViewer'
import { PropertiesEvaluation } from '@/components/evaluation/PropertiesEvaluation'
import { SourcesList } from '@/components/evaluation/SourcesList'
import { AddSourceForm } from '@/components/evaluation/AddSourceForm'
import { TutorialActions } from './_components/TutorialActions'
import { TutorialFooter } from './_components/TutorialFooter'
import { SuccessFeedback } from './_components/SuccessFeedback'
import { ErrorFeedback } from './_components/ErrorFeedback'
import { useUserProgress } from '@/contexts/UserProgressContext'
import { useUserPreferences } from '@/contexts/UserPreferencesContext'
import { useEvaluationSession } from '@/contexts/EvaluationSessionContext'
import { useNextPoliticianContext } from '@/contexts/NextPoliticianContext'
import { PropertyActionItem } from '@/types'
import { actionToEvaluation } from '@/lib/evaluation'
import {
  tutorialSources,
  extractedDataPolitician,
  birthDatePolitician,
  multipleSourcesPolitician,
  genericVsSpecificPolitician,
  deprecateSimplePolitician,
  deprecateWithMetadataPolitician,
} from './tutorialData'

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
  actions: PropertyActionItem[],
  expected: ExpectedEvaluations,
): EvaluationResult {
  const mistakes: string[] = []

  for (const [key, expectedValue] of Object.entries(expected)) {
    const actualValue = actionToEvaluation(actions, key)
    // For existing data (where expected is true = keep), only count as mistake if user deprecated it
    // If the key has no action, that means "keep" which is correct
    if (expectedValue === true && actualValue === undefined) {
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

// Tutorial steps as an enum so we can reorder/insert without renumbering
export enum TutorialStep {
  // Basic tutorial
  Welcome,
  WhyYourHelpMatters,
  SourceDocuments,
  SourcesAndAddSource,
  ExtractedData,
  GiveItATry,
  BirthDateEvaluation,
  BirthDateFeedback,
  MultipleSources,
  MultipleSourcesEvaluation,
  MultipleSourcesFeedback,
  SpecificOverGeneric,
  SpecificOverGenericEvaluation,
  SpecificOverGenericFeedback,
  BasicKeyTakeaways,
  // Advanced tutorial
  AdvancedWelcome,
  ReplacingGenericData,
  DeprecateSimpleEvaluation,
  DataWithMetadata,
  DataWithMetadataEvaluation,
  AdvancedKeyTakeaways,
}

// Step ranges
const BASIC_START = TutorialStep.Welcome
const BASIC_END = TutorialStep.BasicKeyTakeaways
const ADVANCED_START = TutorialStep.AdvancedWelcome
const ADVANCED_END = TutorialStep.AdvancedKeyTakeaways

export interface TutorialContentProps {
  initialStep?: TutorialStep // For testing - allows starting at any step
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
  const { nextHref, loading: nextLoading } = useNextPoliticianContext()

  const startHref = !nextLoading ? (nextHref ?? undefined) : undefined

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
        <Button
          href={startHref}
          size="large"
          fullWidth
          disabled={!startHref}
          onClick={() => startSession()}
        >
          Start Evaluating
        </Button>
      </CenteredCard>
    )
  }

  if (step === TutorialStep.Welcome) {
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

  if (step === TutorialStep.WhyYourHelpMatters) {
    // Why your help matters
    return (
      <CenteredCard emoji="🤖" title="Why Your Help Matters">
        <div className="mb-8 space-y-4">
          <p>
            We&apos;ll show you a politician, their source documents, and data that AI extracted
            from those sources.
          </p>
          <p>
            Your role is to check whether what the AI extracted actually matches what&apos;s written
            in the source document.
          </p>
        </div>
        <TutorialActions
          skipHref={startHref}
          onSkip={() => startSession()}
          buttonText="Got It"
          onNext={nextStep}
        />
      </CenteredCard>
    )
  }

  if (step === TutorialStep.SourceDocuments) {
    // Show source (explanation left, iframe right)
    return (
      <TwoPanel
        left={
          <CenteredCard emoji="📄" title="Source Documents">
            <div className="mb-8 space-y-4">
              <p>
                Let&apos;s start with Jane Doe. On the right is an archived web page about her from
                a government portal.
              </p>
              <p>
                We save copies of these pages so you can verify the data even if the original page
                changes.
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
        right={<SourceViewer pageId="tutorial-page-1" apiBasePath="/api/tutorial-pages" />}
      />
    )
  }

  if (step === TutorialStep.SourcesAndAddSource) {
    // Show sources list with add source form (left), explanation (right)
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
            <SourcesList
              sources={[tutorialSources.page1]}
              activeSourceId={null}
              onViewSource={() => {}}
            />
            <AddSourceForm onSubmit={async () => {}} />
          </div>
        }
        right={
          <CenteredCard emoji="🔗" title="Linked Sources">
            <div className="mb-8 space-y-4">
              <p>
                On the left are the sources linked to Jane. We automatically find and archive what
                we can, but you can always add more yourself.
              </p>
              <p>Just paste a URL and we&apos;ll archive the page and extract data from it too.</p>
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

  if (step === TutorialStep.ExtractedData) {
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
            <SourcesList
              sources={extractedDataPolitician.sources}
              activeSourceId={null}
              onViewSource={() => {}}
            />
            <PropertiesEvaluation
              properties={extractedDataPolitician.properties}
              onAction={() => {}}
              onViewSource={() => {}}
              onHover={() => {}}
              activeSourceId={null}
            />
          </div>
        }
        right={
          <CenteredCard emoji="🗂️" title="Extracted Data">
            <div className="mb-8 space-y-4">
              <p>
                Also on the left, you&apos;ll see data automatically extracted from those sources,
                alongside existing data already known.
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

  if (step === TutorialStep.GiveItATry) {
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

  if (step === TutorialStep.BirthDateEvaluation) {
    // Interactive: birth date evaluation
    return (
      <EvaluationView
        key={`birth-date-${birthDateKey}`}
        politicians={[birthDatePolitician]}
        footer={({ actionsByPolitician }) => {
          const actions = actionsByPolitician.get(birthDatePolitician.id) || []
          return (
            <TutorialFooter
              skipHref={startHref}
              onSkip={() => startSession()}
              actions={actions}
              requiredKeys={Object.keys(birthDateExpected)}
              onSubmit={() => {
                const result = checkEvaluations(actions, birthDateExpected)
                setBirthDateResult(result)
                nextStep()
              }}
              onBack={() => setStep(TutorialStep.GiveItATry)}
            />
          )
        }}
        sourcesApiPath="/api/tutorial-pages"
      />
    )
  }

  if (step === TutorialStep.BirthDateFeedback) {
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
          setStep(TutorialStep.BirthDateEvaluation)
        }}
      />
    )
  }

  if (step === TutorialStep.MultipleSources) {
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

  if (step === TutorialStep.MultipleSourcesEvaluation) {
    // Interactive: positions evaluation
    return (
      <EvaluationView
        key={`multiple-sources-${multipleSourcesKey}`}
        politicians={[multipleSourcesPolitician]}
        footer={({ actionsByPolitician }) => {
          const actions = actionsByPolitician.get(multipleSourcesPolitician.id) || []
          return (
            <TutorialFooter
              skipHref={startHref}
              onSkip={() => startSession()}
              actions={actions}
              requiredKeys={Object.keys(multipleSourcesExpected)}
              onSubmit={() => {
                const result = checkEvaluations(actions, multipleSourcesExpected)
                setMultipleSourcesResult(result)
                nextStep()
              }}
              onBack={() => setStep(TutorialStep.MultipleSources)}
            />
          )
        }}
        sourcesApiPath="/api/tutorial-pages"
      />
    )
  }

  if (step === TutorialStep.MultipleSourcesFeedback) {
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
          setStep(TutorialStep.MultipleSourcesEvaluation)
        }}
      />
    )
  }

  if (step === TutorialStep.SpecificOverGeneric) {
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

  if (step === TutorialStep.SpecificOverGenericEvaluation) {
    // Interactive: generic vs specific evaluation
    return (
      <EvaluationView
        key={`generic-vs-specific-${genericVsSpecificKey}`}
        politicians={[genericVsSpecificPolitician]}
        footer={({ actionsByPolitician }) => {
          const actions = actionsByPolitician.get(genericVsSpecificPolitician.id) || []
          return (
            <TutorialFooter
              skipHref={startHref}
              onSkip={() => startSession()}
              actions={actions}
              requiredKeys={genericVsSpecificRequiredKeys}
              onSubmit={() => {
                const result = checkEvaluations(actions, genericVsSpecificExpected)
                setGenericVsSpecificResult(result)
                nextStep()
              }}
              onBack={() => setStep(TutorialStep.SpecificOverGeneric)}
            />
          )
        }}
        sourcesApiPath="/api/tutorial-pages"
      />
    )
  }

  if (step === TutorialStep.SpecificOverGenericFeedback) {
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
          setStep(TutorialStep.SpecificOverGenericEvaluation)
        }}
      />
    )
  }

  if (step === TutorialStep.BasicKeyTakeaways) {
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

  // ============ ADVANCED TUTORIAL STEPS ============
  if (step === TutorialStep.AdvancedWelcome) {
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

  if (step === TutorialStep.ReplacingGenericData) {
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

  if (step === TutorialStep.DeprecateSimpleEvaluation) {
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
      <EvaluationView
        key={`deprecate-simple-${deprecateSimpleKey}`}
        politicians={[deprecateSimplePolitician]}
        footer={({ actionsByPolitician }) => {
          const actions = actionsByPolitician.get(deprecateSimplePolitician.id) || []
          return (
            <TutorialFooter
              skipHref={startHref}
              onSkip={() => startSession()}
              actions={actions}
              requiredKeys={deprecateSimpleRequiredKeys}
              onSubmit={() => {
                const result = checkEvaluations(actions, deprecateSimpleExpected)
                setDeprecateSimpleResult(result)
              }}
              onBack={() => setStep(TutorialStep.ReplacingGenericData)}
            />
          )
        }}
        sourcesApiPath="/api/tutorial-pages"
      />
    )
  }

  if (step === TutorialStep.DataWithMetadata) {
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

  if (step === TutorialStep.DataWithMetadataEvaluation) {
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
      <EvaluationView
        key={`deprecate-metadata-${deprecateWithMetadataKey}`}
        politicians={[deprecateWithMetadataPolitician]}
        footer={({ actionsByPolitician }) => {
          const actions = actionsByPolitician.get(deprecateWithMetadataPolitician.id) || []
          return (
            <TutorialFooter
              skipHref={startHref}
              onSkip={() => startSession()}
              actions={actions}
              requiredKeys={deprecateWithMetadataRequiredKeys}
              onSubmit={() => {
                const result = checkEvaluations(actions, deprecateWithMetadataExpected)
                setDeprecateWithMetadataResult(result)
              }}
              onBack={() => setStep(TutorialStep.DataWithMetadata)}
            />
          )
        }}
        sourcesApiPath="/api/tutorial-pages"
      />
    )
  }

  if (step === TutorialStep.AdvancedKeyTakeaways) {
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
