import { useCallback, useState, RefObject } from 'react'
import { highlightTextInScope, scrollToFirstHighlight } from '@/lib/textHighlighter'

/**
 * Creates a highlight function for text within iframes
 */
function useIframeHighlighter(iframeRef: RefObject<HTMLIFrameElement | null>) {
  return useCallback(
    async (searchText: string): Promise<number> => {
      if (!iframeRef.current?.contentDocument) {
        console.warn('Iframe document not available for highlighting')
        return 0
      }

      try {
        const document = iframeRef.current.contentDocument

        let matchCount = 0

        if (searchText.trim()) {
          // Add new highlights - use the iframe's body as the scope
          const root = document.body || document.documentElement
          matchCount = highlightTextInScope(document, root, searchText)

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
 */
export function useIframeAutoHighlight(
  iframeRef: RefObject<HTMLIFrameElement | null>,
  proofLine: string | null,
) {
  const [isIframeLoaded, setIsIframeLoaded] = useState(false)
  const highlightText = useIframeHighlighter(iframeRef)

  /**
   * Handler for iframe load events
   */
  const handleIframeLoad = useCallback(() => {
    setIsIframeLoaded(true)

    // Auto-highlight if proof line is available
    if (proofLine) {
      highlightText(proofLine)
    }
  }, [proofLine, highlightText])

  /**
   * Handler when proof line changes
   */
  const handleProofLineChange = useCallback(
    (newProofLine: string | null) => {
      if (isIframeLoaded && newProofLine) {
        highlightText(newProofLine)
      }
    },
    [isIframeLoaded, highlightText],
  )

  return {
    isIframeLoaded,
    handleIframeLoad,
    handleProofLineChange,
  }
}
