import { useCallback, useState, RefObject } from 'react';
import {
  highlightTextInScope,
  scrollToFirstHighlight
} from '@/lib/textHighlighter';

interface UseIframeHighlightingReturn {
  highlightText: (searchText: string) => Promise<number>;
  isHighlighting: boolean;
}

/**
 * Custom hook for managing text highlighting within iframes
 */
export function useIframeHighlighting(
  iframeRef: RefObject<HTMLIFrameElement | null>
): UseIframeHighlightingReturn {
  const [isHighlighting, setIsHighlighting] = useState(false);

  /**
   * Highlights text within the iframe document
   */
  const highlightText = useCallback(async (searchText: string): Promise<number> => {
    if (!iframeRef.current?.contentDocument) {
      console.warn('Iframe document not available for highlighting');
      return 0;
    }

    setIsHighlighting(true);

    try {
      const document = iframeRef.current.contentDocument;
      
      let matchCount = 0;
      
      if (searchText.trim()) {
        // Add new highlights - use the iframe's body as the scope
        const root = document.body || document.documentElement;
        matchCount = highlightTextInScope(document, root, searchText);
        
        // Scroll to first match if any found
        if (matchCount > 0) {
          // Scroll immediately after highlights are applied
          scrollToFirstHighlight(document);
        }
      }
      
      return matchCount;
    } catch (error) {
      console.error('Error highlighting text in iframe:', error);
      return 0;
    } finally {
      setIsHighlighting(false);
    }
  }, [iframeRef]);


  return {
    highlightText,
    isHighlighting
  };
}

/**
 * Hook for managing iframe load state and automatic highlighting
 */
export function useIframeAutoHighlight(
  iframeRef: RefObject<HTMLIFrameElement | null>,
  proofLine: string | null
) {
  const [isIframeLoaded, setIsIframeLoaded] = useState(false);
  const highlighting = useIframeHighlighting(iframeRef);

  /**
   * Handler for iframe load events
   */
  const handleIframeLoad = useCallback(() => {
    setIsIframeLoaded(true);
    
    // Auto-highlight if proof line is available
    if (proofLine) {
      highlighting.highlightText(proofLine);
    }
  }, [proofLine, highlighting, iframeRef]);

  /**
   * Handler when proof line changes
   */
  const handleProofLineChange = useCallback((newProofLine: string | null) => {
    if (isIframeLoaded && newProofLine) {
      highlighting.highlightText(newProofLine);
    }
  }, [isIframeLoaded, highlighting]);

  return {
    ...highlighting,
    isIframeLoaded,
    handleIframeLoad,
    handleProofLineChange
  };
}
