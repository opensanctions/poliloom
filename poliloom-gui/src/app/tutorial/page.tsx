'use client'

import { useState, useRef, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Header } from '@/components/Header'
import { NotificationPage } from '@/components/NotificationPage'
import { Button } from '@/components/Button'
import { Anchor } from '@/components/Anchor'
import { PropertiesEvaluation } from '@/components/PropertiesEvaluation'
import { useTutorial } from '@/contexts/TutorialContext'
import { useIframeAutoHighlight } from '@/hooks/useIframeHighlighting'
import { highlightTextInScope } from '@/lib/textHighlighter'
import { useArchivedPageCache } from '@/contexts/ArchivedPageContext'
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
const position1Property = getProperty('position1')
const position2Property = getProperty('position2')

function TutorialExplanation({
  emoji,
  title,
  description,
  secondaryDescription,
}: {
  emoji: string
  title: string
  description: string
  secondaryDescription?: string
}) {
  return (
    <div className="flex items-center justify-center min-h-0 flex-1 bg-gray-50 h-full">
      <div className="text-center max-w-md p-8">
        <div className="text-6xl mb-6">{emoji}</div>
        <h1 className="text-3xl font-bold text-gray-900 mb-4">{title}</h1>
        <div className="text-lg text-gray-600">
          <p>{description}</p>
          {secondaryDescription && <p className="mt-4">{secondaryDescription}</p>}
        </div>
      </div>
    </div>
  )
}

// Step content that shows properties and archived page
function EvaluationStep({
  properties,
  showArchivedPage,
  showLeftExplanation,
  showRightExplanation,
  isInteractive,
  explanation,
  onNext,
}: {
  properties: Property[]
  showArchivedPage: boolean
  showLeftExplanation: boolean
  showRightExplanation: boolean
  isInteractive: boolean
  explanation: { emoji: string; title: string; description: string; secondaryDescription?: string }
  onNext: () => void
}) {
  const [evaluations, setEvaluations] = useState<Map<string, boolean>>(new Map())
  const [selectedArchivedPage, setSelectedArchivedPage] = useState<ArchivedPageResponse | null>(
    () => {
      if (!showArchivedPage) return null
      const first = properties.find((p) => p.archived_page)
      return first?.archived_page || archivedPages.page1
    },
  )
  const [selectedQuotes, setSelectedQuotes] = useState<string[] | null>(() => {
    if (!showArchivedPage) return null
    const first = properties.find((p) => p.archived_page)
    return first?.supporting_quotes || null
  })

  const iframeRef = useRef<HTMLIFrameElement | null>(null)
  const leftPanelRef = useRef<HTMLDivElement | null>(null)
  const archivedPageCache = useArchivedPageCache()
  const { isIframeLoaded, handleIframeLoad, handleQuotesChange } = useIframeAutoHighlight(
    iframeRef,
    selectedQuotes,
  )

  useEffect(() => {
    if (leftPanelRef.current && selectedQuotes && selectedQuotes.length > 0) {
      highlightTextInScope(document, leftPanelRef.current, selectedQuotes)
    }
    if (isIframeLoaded && selectedQuotes && selectedQuotes.length > 0) {
      handleQuotesChange(selectedQuotes)
    }
  }, [selectedQuotes, isIframeLoaded, handleQuotesChange])

  const handleEvaluate = (propertyId: string, action: 'accept' | 'reject') => {
    if (!isInteractive) return
    setEvaluations((prev) => {
      const newMap = new Map(prev)
      const currentValue = newMap.get(propertyId)
      const targetValue = action === 'accept'
      if (currentValue === targetValue) {
        newMap.delete(propertyId)
      } else {
        newMap.set(propertyId, targetValue)
      }
      return newMap
    })
  }

  const handlePropertyHover = (property: Property) => {
    if (
      property.archived_page &&
      selectedArchivedPage?.id === property.archived_page.id &&
      property.supporting_quotes?.length
    ) {
      setSelectedQuotes(property.supporting_quotes)
    }
  }

  const hasEvaluations = evaluations.size > 0

  return (
    <>
      <Header />
      <div className="grid grid-cols-[46rem_1fr] bg-gray-50 min-h-0">
        <div className="shadow-lg grid grid-rows-[1fr_auto] min-h-0">
          <div ref={leftPanelRef} className="overflow-y-auto min-h-0 p-6">
            <div className="mb-6">
              <div className="text-sm text-indigo-600 font-medium mb-2">Tutorial Mode</div>
              <h1 className="text-2xl font-bold text-gray-900 mb-2">
                <a
                  href={`https://www.wikidata.org/wiki/${tutorialData.politician.wikidataId}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:underline"
                >
                  {tutorialData.politician.name}{' '}
                  <span className="text-gray-500 font-normal">
                    ({tutorialData.politician.wikidataId})
                  </span>
                </a>
              </h1>
            </div>

            {showLeftExplanation ? (
              <TutorialExplanation {...explanation} />
            ) : (
              properties.length > 0 && (
                <PropertiesEvaluation
                  properties={properties}
                  evaluations={evaluations}
                  onAction={isInteractive ? handleEvaluate : () => {}}
                  onShowArchived={(property) => {
                    if (property.archived_page && showArchivedPage) {
                      setSelectedArchivedPage(property.archived_page)
                      setSelectedQuotes(property.supporting_quotes || null)
                    }
                  }}
                  onHover={handlePropertyHover}
                  activeArchivedPageId={selectedArchivedPage?.id || null}
                />
              )
            )}
          </div>

          <div className="p-6 border-t border-gray-200">
            <div className="flex justify-between items-center">
              <Anchor href="/evaluate" className="text-gray-500 hover:text-gray-700 font-medium">
                Skip Tutorial
              </Anchor>
              <Button
                onClick={onNext}
                disabled={isInteractive && !hasEvaluations}
                className="px-6 py-3"
              >
                {isInteractive ? 'Continue' : 'Next'}
              </Button>
            </div>
          </div>
        </div>

        <div className="bg-gray-50 border-l border-gray-200 overflow-hidden min-h-0">
          {showRightExplanation ? (
            <TutorialExplanation {...explanation} />
          ) : showArchivedPage && selectedArchivedPage ? (
            <iframe
              ref={iframeRef}
              src={`/api/tutorial-pages/${selectedArchivedPage.id}/html`}
              className="w-full h-full border-0"
              title="Archived Page"
              sandbox="allow-scripts allow-same-origin"
              onLoad={() => {
                archivedPageCache.markPageAsLoaded(selectedArchivedPage.id)
                handleIframeLoad()
              }}
            />
          ) : (
            <TutorialExplanation {...explanation} />
          )}
        </div>
      </div>
    </>
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

  // Step 0: Intro
  if (step === 0) {
    return (
      <NotificationPage
        emoji="👋"
        title="Welcome to PoliLoom!"
        description={
          <>
            <p>
              You&apos;re about to help build accurate, open political data by verifying information
              extracted from official sources.
            </p>
            <p className="mt-4">Let&apos;s take a quick tour to show you how it works.</p>
          </>
        }
      >
        <Button onClick={nextStep} className="px-6 py-3 w-full">
          Let&apos;s Go
        </Button>
        <Anchor
          href="/evaluate"
          className="inline-flex items-center justify-center px-6 py-3 w-full text-gray-700 font-medium hover:bg-gray-100 rounded-md transition-colors"
        >
          Skip Tutorial
        </Anchor>
      </NotificationPage>
    )
  }

  // Step 1: Archived page explanation
  if (step === 1) {
    return (
      <EvaluationStep
        key={1}
        properties={[]}
        showArchivedPage={true}
        showLeftExplanation={true}
        showRightExplanation={false}
        isInteractive={false}
        explanation={{
          emoji: '📄',
          title: 'Source Documents',
          description:
            "On the right side, you'll see archived web pages from government portals, Wikipedia, and other official sources.",
          secondaryDescription:
            'These are the original documents where we found information about politicians. We save copies so you can verify the data even if the original page changes.',
        }}
        onNext={nextStep}
      />
    )
  }

  // Step 2: Structured data explanation
  if (step === 2) {
    return (
      <EvaluationStep
        key={2}
        properties={[birthDateProperty]}
        showArchivedPage={false}
        showLeftExplanation={false}
        showRightExplanation={true}
        isInteractive={false}
        explanation={{
          emoji: '🗂️',
          title: 'Extracted Data',
          description:
            'On the left, you see structured data that was automatically extracted from the source documents using AI.',
          secondaryDescription:
            'Your job is to verify if this extracted data is correct by checking it against the source document.',
        }}
        onNext={nextStep}
      />
    )
  }

  // Step 3: Try yourself (single property)
  if (step === 3) {
    return (
      <EvaluationStep
        key={3}
        properties={[birthDateProperty]}
        showArchivedPage={true}
        showLeftExplanation={false}
        showRightExplanation={false}
        isInteractive={true}
        explanation={{
          emoji: '✨',
          title: 'Try It Yourself',
          description: "Now it's your turn! Review the data and click Accept or Reject.",
        }}
        onNext={nextStep}
      />
    )
  }

  // Step 4: Multiple pages explanation
  if (step === 4) {
    return (
      <EvaluationStep
        key={4}
        properties={[position1Property, position2Property]}
        showArchivedPage={false}
        showLeftExplanation={false}
        showRightExplanation={true}
        isInteractive={false}
        explanation={{
          emoji: '📚',
          title: 'Multiple Sources',
          description: 'Sometimes information comes from different source documents.',
          secondaryDescription:
            'Click the "View" button next to any data item to see its source document.',
        }}
        onNext={nextStep}
      />
    )
  }

  // Step 5: Try yourself (multiple properties)
  if (step === 5) {
    return (
      <EvaluationStep
        key={5}
        properties={[position1Property, position2Property]}
        showArchivedPage={true}
        showLeftExplanation={false}
        showRightExplanation={false}
        isInteractive={true}
        explanation={{
          emoji: '🔄',
          title: 'Try Multiple Sources',
          description: 'Review these positions from different sources.',
        }}
        onNext={nextStep}
      />
    )
  }

  // Step 6: Complete
  return (
    <NotificationPage
      emoji="🎉"
      title="Tutorial Complete!"
      description={
        <>
          <p>Great job! You now know how to:</p>
          <ul className="text-left mt-4 space-y-2">
            <li>• View source documents with highlighted text</li>
            <li>• Review extracted data and accept or reject it</li>
            <li>• Handle multiple sources for different data</li>
          </ul>
        </>
      }
    >
      <Button onClick={handleComplete} className="px-6 py-3 w-full">
        Start Evaluating
      </Button>
    </NotificationPage>
  )
}
