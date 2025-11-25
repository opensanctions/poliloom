import { useCallback, useState, RefObject } from 'react'
import { highlightTextInScope, scrollToFirstHighlight } from '@/lib/textHighlighter'

/**
 * Creates a highlight function for text within iframes
 * Accepts either a single search text or an array of search texts
 */
function useIframeHighlighter(iframeRef: RefObject<HTMLIFrameElement | null>) {
  return useCallback(
    async (searchTexts: string | string[]): Promise<number> => {
      if (!iframeRef.current?.contentDocument) {
        console.warn('Iframe document not available for highlighting')
        return 0
      }

      try {
        const document = iframeRef.current.contentDocument
        const texts = Array.isArray(searchTexts) ? searchTexts : [searchTexts]
        const hasValidText = texts.some((t) => t.trim())

        let matchCount = 0

        if (hasValidText) {
          // Add new highlights - use the iframe's body as the scope
          const root = document.body || document.documentElement
          matchCount = highlightTextInScope(document, root, texts)

          // Scroll to first match if any found
          if (matchCount > 0) {
            scrollToFirstHighlight(document)
          }
        }

        return matchCount
      } catch (error) {
        console.error('Error highlighting text in iframe:', error)
        return 0
      }
    },
    [iframeRef],
  )
}

/**
 * Hook for managing iframe load state and automatic highlighting
 * Supports multiple supporting quotes to be highlighted simultaneously
 */
export function useIframeAutoHighlight(
  iframeRef: RefObject<HTMLIFrameElement | null>,
  supportingQuotes: string[] | null,
) {
  const [isIframeLoaded, setIsIframeLoaded] = useState(false)
  const highlightText = useIframeHighlighter(iframeRef)

  /**
   * Handler for iframe load events
   */
  const handleIframeLoad = useCallback(() => {
    setIsIframeLoaded(true)

    // Auto-highlight if supporting quotes are available
    if (supportingQuotes && supportingQuotes.length > 0) {
      highlightText(supportingQuotes)
    }
  }, [supportingQuotes, highlightText])

  /**
   * Handler when supporting quotes change
   */
  const handleQuotesChange = useCallback(
    (newQuotes: string[] | null) => {
      if (isIframeLoaded && newQuotes && newQuotes.length > 0) {
        highlightText(newQuotes)
      }
    },
    [isIframeLoaded, highlightText],
  )

  return {
    isIframeLoaded,
    handleIframeLoad,
    handleQuotesChange,
  }
}
