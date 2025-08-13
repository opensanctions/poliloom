/**
 * Modern text highlighting using the CSS Custom Highlight API
 * Supports exact text matching and cross-element highlighting
 */

const HIGHLIGHT_NAME = 'poliloom';
const MAX_NODE_WINDOW = 20;
const PUNCTUATION_REGEX = /^\s*[.!?,:;]/;
const WHITESPACE_REGEX = /\s/;
const EXCLUDED_TAG_NAMES = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT']);

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
 * Escapes special regex characters in a string for literal matching
 */
function escapeRegexChars(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Creates a safe range with bounds checking
 */
function createSafeRange(document: Document, textNode: Text, start: number, end: number): Range {
  const range = document.createRange();
  const textLength = textNode.textContent?.length || 0;
  range.setStart(textNode, Math.min(start, textLength));
  range.setEnd(textNode, Math.min(end, textLength));
  return range;
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
        return parent && EXCLUDED_TAG_NAMES.has(parent.tagName)
          ? NodeFilter.FILTER_REJECT
          : NodeFilter.FILTER_ACCEPT;
      }
    }
  );
}

/**
 * Maps a position in normalized text back to the original text position
 */
function mapNormalizedToOriginalPosition(originalText: string, normalizedPosition: number): number {
  let normalizedIndex = 0;
  let originalIndex = 0;
  
  while (originalIndex < originalText.length && normalizedIndex < normalizedPosition) {
    if (WHITESPACE_REGEX.test(originalText[originalIndex])) {
      // Skip consecutive whitespace in original text
      while (originalIndex + 1 < originalText.length && WHITESPACE_REGEX.test(originalText[originalIndex + 1])) {
        originalIndex++;
      }
      normalizedIndex++;
    } else {
      normalizedIndex++;
    }
    originalIndex++;
  }
  
  return originalIndex;
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
  
  // Use regex for case-insensitive search to find all matches
  const regex = new RegExp(escapeRegexChars(normalizedSearch), 'gi');
  const match = regex.exec(normalizedText);
  
  if (!match) {
    return [];
  }
  
  // Map normalized positions back to original text positions
  const actualStart = mapNormalizedToOriginalPosition(text, match.index);
  const actualEnd = mapNormalizedToOriginalPosition(text, match.index + normalizedSearch.length);
  
  // Create a range for the matched text
  const range = createSafeRange(document, textNode, actualStart, actualEnd);
  
  return [range];
}

/**
 * Combines text from consecutive nodes with smart spacing
 */
function combineNodeTexts(nodes: Text[]): { 
  combinedText: string; 
  nodeMap: Array<{ node: Text; startPos: number; endPos: number }> 
} {
  return nodes.reduce((acc, node) => {
    const nodeText = node.textContent || '';
    
    // Skip empty or whitespace-only nodes for matching purposes
    if (!nodeText.trim()) {
      return acc;
    }
    
    const startPos = acc.combinedText.length;
    
    // Add space between nodes, but not before punctuation
    if (acc.combinedText && !PUNCTUATION_REGEX.test(nodeText)) {
      acc.combinedText += ' ';
    }
    acc.combinedText += nodeText;
    
    const endPos = acc.combinedText.length;
    acc.nodeMap.push({ node, startPos, endPos });
    
    return acc;
  }, { combinedText: '', nodeMap: [] as Array<{ node: Text; startPos: number; endPos: number }> });
}

/**
 * Creates ranges for nodes that overlap with a text match
 */
function createOverlappingRanges(
  document: Document,
  nodeMap: Array<{ node: Text; startPos: number; endPos: number }>,
  combinedText: string,
  matchStart: number,
  matchEnd: number
): Range[] {
  return nodeMap
    .filter(nodeInfo => {
      const normalizedNodeStart = normalizeWhitespace(combinedText.substring(0, nodeInfo.startPos)).length;
      const normalizedNodeEnd = normalizeWhitespace(combinedText.substring(0, nodeInfo.endPos)).length;
      
      // Check if this node overlaps with the match
      return normalizedNodeEnd > matchStart && normalizedNodeStart < matchEnd;
    })
    .map(nodeInfo => {
      const range = document.createRange();
      range.selectNode(nodeInfo.node);
      return range;
    });
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
  
  // Try different sliding windows of nodes to find matches
  for (let i = 0; i < textNodes.length; i++) {
    const windowNodes = textNodes.slice(i, Math.min(i + MAX_NODE_WINDOW, textNodes.length));
    const { combinedText, nodeMap } = combineNodeTexts(windowNodes);
    
    if (!combinedText.trim()) continue;
    
    const normalizedCombined = normalizeWhitespace(combinedText).toLowerCase();
    const matchStart = normalizedCombined.indexOf(normalizedSearch);
    
    if (matchStart !== -1) {
      const matchEnd = matchStart + normalizedSearch.length;
      return createOverlappingRanges(document, nodeMap, combinedText, matchStart, matchEnd);
    }
  }
  
  return [];
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

