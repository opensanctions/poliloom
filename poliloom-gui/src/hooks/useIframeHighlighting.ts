import { useCallback, useState, RefObject } from 'react';
import {
  highlightTextInScope,
  clearHighlights,
  scrollToFirstHighlight
} from '@/lib/textHighlighter';

interface UseIframeHighlightingReturn {
  highlightText: (searchText: string) => Promise<number>;
  clearAllHighlights: () => void;
  isHighlighting: boolean;
  highlightCount: number;
}

/**
 * Custom hook for managing text highlighting within iframes
 */
export function useIframeHighlighting(
  iframeRef: RefObject<HTMLIFrameElement | null>
): UseIframeHighlightingReturn {
  const [isHighlighting, setIsHighlighting] = useState(false);
  const [highlightCount, setHighlightCount] = useState(0);

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
      
      // Clear any existing highlights
      clearHighlights();
      
      let matchCount = 0;
      
      if (searchText.trim()) {
        // Add new highlights - use the iframe's body as the scope
        const root = document.body || document.documentElement;
        matchCount = highlightTextInScope(document, root, searchText);
        
        // Scroll to first match if any found
        if (matchCount > 0) {
          // Small delay to ensure highlights are applied before scrolling
          setTimeout(() => {
            scrollToFirstHighlight(document);
          }, 50);
        }
      }
      
      setHighlightCount(matchCount);
      return matchCount;
    } catch (error) {
      console.error('Error highlighting text in iframe:', error);
      setHighlightCount(0);
      return 0;
    } finally {
      setIsHighlighting(false);
    }
  }, [iframeRef]);

  /**
   * Clears all highlights from the iframe document
   */
  const clearAllHighlights = useCallback(() => {
    if (!iframeRef.current?.contentDocument) {
      return;
    }

    try {
      clearHighlights();
      setHighlightCount(0);
    } catch (error) {
      console.error('Error clearing highlights in iframe:', error);
    }
  }, [iframeRef]);

  return {
    highlightText,
    clearAllHighlights,
    isHighlighting,
    highlightCount
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
    
    // Inject highlight styles into the iframe from the parent document
    if (iframeRef.current?.contentDocument) {
      const iframeDoc = iframeRef.current.contentDocument;
      
      // Check if styles are already injected
      if (!iframeDoc.querySelector('style[data-poliloom-highlight]')) {
        const style = iframeDoc.createElement('style');
        style.setAttribute('data-poliloom-highlight', 'true');
        style.textContent = `::highlight(poliloom) { background-color: yellow; }`;
        iframeDoc.head.appendChild(style);
      }
    }
    
    // Auto-highlight if proof line is available
    if (proofLine) {
      // Small delay to ensure iframe content is fully loaded and styles are applied
      setTimeout(() => {
        highlighting.highlightText(proofLine);
      }, 200);
    }
  }, [proofLine, highlighting, iframeRef]);

  /**
   * Handler when proof line changes
   */
  const handleProofLineChange = useCallback((newProofLine: string | null) => {
    if (isIframeLoaded && newProofLine) {
      highlighting.highlightText(newProofLine);
    } else if (isIframeLoaded && !newProofLine) {
      highlighting.clearAllHighlights();
    }
  }, [isIframeLoaded, highlighting]);

  return {
    ...highlighting,
    isIframeLoaded,
    handleIframeLoad,
    handleProofLineChange
  };
}