/**
 * Modern text highlighting using the CSS Custom Highlight API
 * Supports exact text matching and cross-element highlighting
 */

const HIGHLIGHT_NAME = 'poliloom';

/**
 * Safely strips HTML tags from text using DOMParser
 */
export function stripHtmlTags(html: string): string {
  if (!html || !html.trim()) {
    return '';
  }
  
  try {
    const doc = new DOMParser().parseFromString(html, 'text/html');
    return normalizeWhitespace(doc.body.textContent || '');
  } catch (error) {
    console.warn('Error parsing HTML, falling back to regex:', error);
    return normalizeWhitespace(html.replace(/<[^>]*>/g, ''));
  }
}

/**
 * Normalizes whitespace by collapsing multiple spaces and trimming
 */
export function normalizeWhitespace(text: string): string {
  return text.replace(/\s+/g, ' ').trim();
}

/**
 * Creates a text node walker that skips script/style elements
 */
function createTextNodeWalker(document: Document, root: Node): TreeWalker {
  return document.createTreeWalker(
    root,
    NodeFilter.SHOW_TEXT,
    {
      acceptNode: (node: Node) => {
        const parent = node.parentElement;
        if (parent && (
          parent.tagName === 'SCRIPT' ||
          parent.tagName === 'STYLE' ||
          parent.tagName === 'NOSCRIPT'
        )) {
          return NodeFilter.FILTER_REJECT;
        }
        return NodeFilter.FILTER_ACCEPT;
      }
    }
  );
}

/**
 * Finds exact text matches within a single text node using CSS Custom Highlight API
 */
function highlightExactMatches(
  document: Document,
  textNode: Text,
  searchText: string
): Range[] {
  const text = textNode.textContent || '';
  const normalizedText = normalizeWhitespace(text);
  const normalizedSearch = normalizeWhitespace(searchText);
  
  // Case-insensitive search for the exact text
  const searchIndex = normalizedText.toLowerCase().indexOf(normalizedSearch.toLowerCase());
  
  if (searchIndex === -1) {
    return [];
  }
  
  // Find the actual position in the original text (accounting for whitespace differences)
  let actualStart = 0;
  let normalizedPos = 0;
  
  for (let i = 0; i < text.length; i++) {
    if (normalizedPos === searchIndex) {
      actualStart = i;
      break;
    }
    if (text[i].match(/\s/)) {
      // Skip consecutive whitespace in original
      while (i + 1 < text.length && text[i + 1].match(/\s/)) {
        i++;
      }
      normalizedPos++; // Count as single space in normalized
    } else {
      normalizedPos++;
    }
  }
  
  // Find the actual end position
  let actualEnd = actualStart;
  let matchedLength = 0;
  
  for (let i = actualStart; i < text.length && matchedLength < normalizedSearch.length; i++) {
    if (text[i].match(/\s/)) {
      // Skip consecutive whitespace
      while (i + 1 < text.length && text[i + 1].match(/\s/) && matchedLength < normalizedSearch.length) {
        i++;
      }
      matchedLength++;
    } else {
      matchedLength++;
    }
    actualEnd = i + 1;
  }
  
  // Create a range for the matched text
  const range = document.createRange();
  range.setStart(textNode, actualStart);
  range.setEnd(textNode, actualEnd);
  
  return [range];
}

/**
 * Handles text that spans multiple text nodes using CSS Custom Highlight API
 */
function highlightCrossNodeText(
  document: Document,
  textNodes: Text[],
  searchText: string
): Range[] {
  const normalizedSearch = normalizeWhitespace(searchText).toLowerCase();
  const ranges: Range[] = [];
  
  // Build a map of text nodes and their cumulative text
  for (let i = 0; i < textNodes.length; i++) {
    let combinedText = '';
    const nodeInfos: Array<{ node: Text; text: string; startPos: number; endPos: number }> = [];
    
    // Try combining consecutive text nodes
    for (let j = i; j < Math.min(i + 20, textNodes.length); j++) {
      const nodeText = textNodes[j].textContent || '';
      
      // Skip empty or whitespace-only nodes for matching purposes
      if (!nodeText.trim()) {
        continue;
      }
      
      const startPos = combinedText.length;
      
      // Add space between nodes, but not before punctuation
      if (combinedText && !nodeText.match(/^\s*[.!?,:;]/)) {
        combinedText += ' ';
      }
      combinedText += nodeText;
      
      const endPos = combinedText.length;
      nodeInfos.push({ node: textNodes[j], text: nodeText, startPos, endPos });
      
      const normalizedCombined = normalizeWhitespace(combinedText).toLowerCase();
      
      if (normalizedCombined.includes(normalizedSearch)) {
        // Found a match - create ranges for nodes that contribute to the match
        const matchStart = normalizedCombined.indexOf(normalizedSearch);
        const matchEnd = matchStart + normalizedSearch.length;
        
        // Only highlight nodes that actually contribute to the matching text
        for (const nodeInfo of nodeInfos) {
          const normalizedNodeStart = normalizeWhitespace(combinedText.substring(0, nodeInfo.startPos)).length;
          const normalizedNodeEnd = normalizeWhitespace(combinedText.substring(0, nodeInfo.endPos)).length;
          
          // Check if this node overlaps with the match
          if (normalizedNodeEnd > matchStart && normalizedNodeStart < matchEnd) {
            const range = document.createRange();
            range.selectNode(nodeInfo.node);
            ranges.push(range);
          }
        }
        return ranges;
      }
    }
  }
  
  return ranges;
}

/**
 * Finds and highlights exact text matches within a scope using CSS Custom Highlight API
 * Returns the number of highlights created
 */
export function highlightTextInScope(
  document: Document, 
  scope: Element, 
  searchText: string
): number {
  if (!searchText.trim()) {
    return 0;
  }

  const normalizedSearch = normalizeWhitespace(searchText);
  const walker = createTextNodeWalker(document, scope);
  const textNodes: Text[] = [];
  let node: Node | null;
  
  // Collect all text nodes
  while (node = walker.nextNode()) {
    textNodes.push(node as Text);
  }
  
  let ranges: Range[] = [];
  
  // Try to find exact matches in individual text nodes first
  for (const textNode of textNodes) {
    const nodeRanges = highlightExactMatches(document, textNode, normalizedSearch);
    ranges.push(...nodeRanges);
  }
  
  // If no exact matches found, try to find cross-node matches
  if (ranges.length === 0) {
    ranges = highlightCrossNodeText(document, textNodes, normalizedSearch);
  }
  
  // Create and set the highlight
  if (ranges.length > 0) {
    const highlight = new Highlight(...ranges);
    // Use the document's CSS object instead of the global CSS
    const documentCSS = document.defaultView?.CSS || CSS;
    documentCSS.highlights.set(HIGHLIGHT_NAME, highlight);
  }
  
  return ranges.length;
}




/**
 * Scrolls to the first highlighted range in the document
 */
export function scrollToFirstHighlight(document: Document): boolean {
  const documentCSS = document.defaultView?.CSS || CSS;
  const highlight = documentCSS.highlights.get(HIGHLIGHT_NAME);
  
  if (highlight && highlight.size > 0) {
    // Get the first range from the highlight
    const firstRange = highlight.values().next().value as Range;
    
    if (firstRange && 'getBoundingClientRect' in firstRange) {
      const iframeWindow = document.defaultView || window;
      const scrollContainer = document.body.scrollHeight > document.documentElement.scrollHeight 
        ? document.body 
        : document.documentElement;
      
      const rect = firstRange.getBoundingClientRect();
      const scrollTop = scrollContainer.scrollTop;
      const targetPosition = scrollTop + rect.top - (iframeWindow.innerHeight / 2) + (rect.height / 2);
      
      if (typeof scrollContainer.scrollTo === 'function') {
        scrollContainer.scrollTo({
          top: Math.max(0, targetPosition),
          behavior: 'smooth'
        });
      } else {
        scrollContainer.scrollTop = Math.max(0, targetPosition);
      }
      
      return true;
    }
  }
  
  return false;
}

