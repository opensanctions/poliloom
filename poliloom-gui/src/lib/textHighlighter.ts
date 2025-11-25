/**
 * Text highlighting using the CSS Custom Highlight API
 *
 * Algorithm Overview:
 * This mirrors BeautifulSoup's text extraction where element boundaries are treated
 * as optional whitespace. The approach has two phases:
 *
 * 1. BUILD PHASE: Extract DOM text into a stream of tokens, each being either:
 *    - A character (with position info)
 *    - A space (real whitespace, collapsed)
 *    - A boundary space (virtual, at element transitions - can be skipped or matched)
 *
 * 2. MATCH PHASE: Walk the stream matching against the needle:
 *    - Non-space in needle: skip any boundary spaces, then match the character
 *    - Space in needle: match any space (real or boundary)
 *
 * This cleanly separates DOM traversal from matching logic.
 */

const HIGHLIGHT_NAME = 'poliloom'
const WHITESPACE_REGEX = /\s/
const EXCLUDED_TAG_NAMES = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT'])

// Public utilities kept for tests and callers
export function stripHtmlTags(html: string): string {
  if (!html || !html.trim()) return ''
  try {
    const doc = new DOMParser().parseFromString(html, 'text/html')
    return normalizeWhitespace(doc.body.textContent || '')
  } catch {
    return normalizeWhitespace(html.replace(/<[^>]*>/g, ''))
  }
}

export function normalizeWhitespace(text: string): string {
  return text.replace(/\s+/g, ' ').trim()
}

function isWhitespace(ch: string): boolean {
  return WHITESPACE_REGEX.test(ch)
}

function createTextNodeWalker(document: Document, root: Node): TreeWalker {
  return document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode: (node: Node) => {
      const parent = (node as Text).parentElement
      return parent && EXCLUDED_TAG_NAMES.has(parent.tagName)
        ? NodeFilter.FILTER_REJECT
        : NodeFilter.FILTER_ACCEPT
    },
  })
}

/** A token in the normalized text stream */
interface StreamToken {
  char: string // lowercase character, or ' ' for any whitespace
  node: Text // source text node
  startOffset: number // start position in node
  endOffset: number // end position in node (exclusive)
  isBoundary: boolean // true if this is a virtual boundary space (can be skipped)
}

/**
 * Build a normalized stream of tokens from the DOM.
 * - Collapses consecutive whitespace into single space tokens
 * - Inserts boundary space tokens at element transitions (where no actual whitespace exists)
 * - Lowercases all characters
 */
function buildTokenStream(document: Document, scope: Element): StreamToken[] {
  const walker = createTextNodeWalker(document, scope)
  const tokens: StreamToken[] = []

  let prevWasSpace = true // Treat document start as "after space" to handle leading content
  let prevNode: Text | null = null
  let prevNodeEnd = 0

  let node = walker.nextNode() as Text | null

  while (node) {
    const content = node.textContent || ''

    // Insert boundary space at element transition when:
    // 1. There was a previous node
    // 2. Previous token wasn't a space (real or boundary)
    // 3. Current content doesn't start with whitespace
    if (prevNode !== null && !prevWasSpace && content.length > 0 && !isWhitespace(content[0])) {
      tokens.push({
        char: ' ',
        node: prevNode,
        startOffset: prevNodeEnd,
        endOffset: prevNodeEnd, // Zero-width - points to end of previous node
        isBoundary: true,
      })
      prevWasSpace = true
    }

    // Process characters in this node
    let i = 0
    while (i < content.length) {
      if (isWhitespace(content[i])) {
        // Find end of whitespace run
        let endOffset = i + 1
        while (endOffset < content.length && isWhitespace(content[endOffset])) {
          endOffset++
        }

        // Only emit space if previous wasn't already a space (collapse whitespace)
        if (!prevWasSpace) {
          tokens.push({
            char: ' ',
            node,
            startOffset: i,
            endOffset,
            isBoundary: false,
          })
          prevWasSpace = true
        }
        i = endOffset
      } else {
        tokens.push({
          char: content[i].toLowerCase(),
          node,
          startOffset: i,
          endOffset: i + 1,
          isBoundary: false,
        })
        prevWasSpace = false
        i++
      }
    }

    prevNode = node
    prevNodeEnd = content.length
    node = walker.nextNode() as Text | null
  }

  // Trim trailing spaces
  while (tokens.length > 0 && tokens[tokens.length - 1].char === ' ') {
    tokens.pop()
  }

  return tokens
}

/**
 * Find all matches of searchText in the token stream and return Range objects.
 * - Boundary spaces can match a space in searchText OR be skipped entirely
 * - Real spaces must match a space in searchText
 */
function findRangesAcrossNodes(document: Document, scope: Element, searchText: string): Range[] {
  const needle = normalizeWhitespace(searchText).toLowerCase()
  if (!needle) return []

  const tokens = buildTokenStream(document, scope)
  if (tokens.length === 0) return []

  const ranges: Range[] = []
  let tokenIdx = 0

  while (tokenIdx < tokens.length) {
    // Skip boundary spaces when looking for match start
    if (tokens[tokenIdx].isBoundary) {
      tokenIdx++
      continue
    }

    // Try to match starting at this token
    const match = tryMatch(tokens, tokenIdx, needle)

    if (match) {
      const range = document.createRange()
      range.setStart(match.startNode, match.startOffset)
      range.setEnd(match.endNode, match.endOffset)
      ranges.push(range)
      tokenIdx = match.nextTokenIdx // Continue after match (non-overlapping)
    } else {
      tokenIdx++
    }
  }

  return ranges
}

interface MatchResult {
  startNode: Text
  startOffset: number
  endNode: Text
  endOffset: number
  nextTokenIdx: number
}

/**
 * Try to match the needle starting at the given token index.
 * Returns match info if successful, null otherwise.
 */
function tryMatch(tokens: StreamToken[], startIdx: number, needle: string): MatchResult | null {
  let ti = startIdx // token index
  let ni = 0 // needle index

  let matchStartNode: Text | null = null
  let matchStartOffset = 0
  let matchEndNode: Text | null = null
  let matchEndOffset = 0

  while (ni < needle.length && ti < tokens.length) {
    const expected = needle[ni]
    const token = tokens[ti]

    if (expected === ' ') {
      // Expecting space - must match a space token (real or boundary)
      if (token.char !== ' ') {
        return null // No space where expected
      }

      // Initialize match start if needed
      if (matchStartNode === null) {
        matchStartNode = token.node
        matchStartOffset = token.startOffset
      }

      // Only update match end for real spaces (boundary spaces have zero width)
      if (!token.isBoundary) {
        matchEndNode = token.node
        matchEndOffset = token.endOffset
      }

      ni++
      ti++
    } else {
      // Expecting non-space character
      // First, skip any boundary spaces (they're optional when not matching a space)
      while (ti < tokens.length && tokens[ti].char === ' ' && tokens[ti].isBoundary) {
        ti++
      }

      if (ti >= tokens.length) {
        return null // Ran out of tokens
      }

      const token = tokens[ti]

      if (token.char === ' ') {
        // Hit a real space when expecting a character - no match
        return null
      }

      if (token.char !== expected) {
        // Wrong character
        return null
      }

      // Character matches
      if (matchStartNode === null) {
        matchStartNode = token.node
        matchStartOffset = token.startOffset
      }
      matchEndNode = token.node
      matchEndOffset = token.endOffset

      ni++
      ti++
    }
  }

  // Check if we matched the entire needle
  if (ni === needle.length && matchStartNode !== null && matchEndNode !== null) {
    return {
      startNode: matchStartNode,
      startOffset: matchStartOffset,
      endNode: matchEndNode,
      endOffset: matchEndOffset,
      nextTokenIdx: ti,
    }
  }

  return null
}

/**
 * Highlights text within a scope using the CSS Custom Highlight API
 * Accepts either a single search text or an array of search texts to highlight simultaneously
 * Returns the total number of highlights created
 */
export function highlightTextInScope(
  document: Document,
  scope: Element,
  searchTexts: string | string[],
): number {
  const texts = Array.isArray(searchTexts) ? searchTexts : [searchTexts]
  const validTexts = texts.filter((t) => t.trim())
  if (validTexts.length === 0) return 0

  const allRanges: Range[] = []
  for (const text of validTexts) {
    const ranges = findRangesAcrossNodes(document, scope, text)
    allRanges.push(...ranges)
  }

  if (allRanges.length > 0) {
    const highlight = new Highlight(...allRanges)
    const documentCSS = document.defaultView?.CSS || CSS
    documentCSS.highlights.set(HIGHLIGHT_NAME, highlight)
  }
  return allRanges.length
}

/**
 * Scrolls to the first highlighted range in the document
 */
export function scrollToFirstHighlight(document: Document): boolean {
  const documentCSS = document.defaultView?.CSS || CSS
  const highlight = documentCSS.highlights.get(HIGHLIGHT_NAME)
  if (highlight && highlight.size > 0) {
    const firstRange = highlight.values().next().value as Range
    if (firstRange && 'getBoundingClientRect' in firstRange) {
      const iframeWindow = document.defaultView || window
      const scrollContainer =
        document.body.scrollHeight > document.documentElement.scrollHeight
          ? document.body
          : document.documentElement

      const rect = firstRange.getBoundingClientRect()
      const scrollTop = scrollContainer.scrollTop
      const targetPosition = scrollTop + rect.top - iframeWindow.innerHeight / 2 + rect.height / 2

      if (typeof (scrollContainer as Element).scrollTo === 'function') {
        ;(scrollContainer as Element).scrollTo({
          top: Math.max(0, targetPosition),
          behavior: 'smooth',
        })
      } else {
        ;(scrollContainer as Element).scrollTop = Math.max(0, targetPosition)
      }
      return true
    }
  }
  return false
}
