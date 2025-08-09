/**
 * Utility functions for highlighting text within DOM documents
 */

const HIGHLIGHT_CLASS = 'poliloom-highlight';
const HIGHLIGHT_TAG = 'mark';

/**
 * Escapes special regex characters in a string
 */
function escapeRegExp(string: string): string {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Creates a text node walker that only visits text nodes
 */
function createTextNodeWalker(document: Document, root: Node): TreeWalker {
  return document.createTreeWalker(
    root,
    NodeFilter.SHOW_TEXT,
    {
      acceptNode: (node: Node) => {
        // Skip text nodes inside script, style, and our highlight tags
        const parent = node.parentElement;
        if (parent && (
          parent.tagName === 'SCRIPT' ||
          parent.tagName === 'STYLE' ||
          parent.tagName === 'NOSCRIPT' ||
          parent.classList.contains(HIGHLIGHT_CLASS)
        )) {
          return NodeFilter.FILTER_REJECT;
        }
        return NodeFilter.FILTER_ACCEPT;
      }
    }
  );
}

/**
 * Highlights all occurrences of searchText within the document
 * Returns the number of matches found
 */
export function highlightTextInDocument(document: Document, searchText: string): number {
  if (!searchText.trim()) {
    return 0;
  }

  const walker = createTextNodeWalker(document, document.body || document.documentElement);
  const textNodes: Text[] = [];
  let node: Node | null;

  // Collect all text nodes first to avoid iterator invalidation
  while (node = walker.nextNode()) {
    textNodes.push(node as Text);
  }

  const searchRegex = new RegExp(escapeRegExp(searchText.trim()), 'gi');
  let totalMatches = 0;

  textNodes.forEach(textNode => {
    const text = textNode.textContent || '';
    const matches = Array.from(text.matchAll(searchRegex));
    
    if (matches.length === 0) {
      return;
    }

    totalMatches += matches.length;

    // Create document fragment with highlighted text
    const fragment = document.createDocumentFragment();
    let lastIndex = 0;

    matches.forEach(match => {
      const matchIndex = match.index!;
      const matchText = match[0];

      // Add text before the match
      if (matchIndex > lastIndex) {
        fragment.appendChild(
          document.createTextNode(text.slice(lastIndex, matchIndex))
        );
      }

      // Add highlighted match
      const mark = document.createElement(HIGHLIGHT_TAG);
      mark.className = `${HIGHLIGHT_CLASS} bg-yellow-200 font-semibold`;
      mark.textContent = matchText;
      fragment.appendChild(mark);

      lastIndex = matchIndex + matchText.length;
    });

    // Add remaining text after the last match
    if (lastIndex < text.length) {
      fragment.appendChild(
        document.createTextNode(text.slice(lastIndex))
      );
    }

    // Replace the original text node with the highlighted fragment
    textNode.parentNode?.replaceChild(fragment, textNode);
  });

  return totalMatches;
}

/**
 * Removes all highlights from the document
 */
export function clearHighlights(document: Document): void {
  const highlights = document.querySelectorAll(`.${HIGHLIGHT_CLASS}`);
  
  highlights.forEach(highlight => {
    const parent = highlight.parentNode;
    if (parent) {
      // Replace the highlight element with its text content
      const textNode = document.createTextNode(highlight.textContent || '');
      parent.replaceChild(textNode, highlight);
      
      // Normalize adjacent text nodes
      parent.normalize();
    }
  });
}

/**
 * Scrolls to the first highlighted element in the document
 */
export function scrollToFirstHighlight(document: Document): boolean {
  const firstHighlight = document.querySelector(`.${HIGHLIGHT_CLASS}`) as HTMLElement;
  
  if (firstHighlight) {
    // Get the iframe's window context
    const iframeWindow = document.defaultView || window;
    
    // Get the scroll container (body or documentElement of the iframe)
    const scrollContainer = document.body.scrollHeight > document.documentElement.scrollHeight 
      ? document.body 
      : document.documentElement;
    
    // Calculate position relative to the iframe document
    const rect = firstHighlight.getBoundingClientRect();
    const scrollTop = scrollContainer.scrollTop;
    const targetPosition = scrollTop + rect.top - (iframeWindow.innerHeight / 2) + (rect.height / 2);
    
    // Scroll only within the iframe's context
    scrollContainer.scrollTo({
      top: Math.max(0, targetPosition),
      behavior: 'smooth'
    });
    
    return true;
  }
  
  return false;
}

