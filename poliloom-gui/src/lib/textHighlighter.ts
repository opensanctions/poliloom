/**
 * Modern text highlighting using the CSS Custom Highlight API
 * Simplified: single-pass, cross-node, whitespace-coalescing matcher
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

/**
 * Single-pass finder that produces precise ranges spanning across nodes.
 * - Case-insensitive
 * - Collapses any run of document whitespace into a single matcher unit
 */
function findRangesAcrossNodes(document: Document, scope: Element, searchText: string): Range[] {
  const needle = normalizeWhitespace(searchText).toLowerCase()
  if (!needle) return []

  const walker = createTextNodeWalker(document, scope)
  let node = walker.nextNode() as Text | null

  const ranges: Range[] = []
  let matchIdx = 0
  let matchStartNode: Text | null = null
  let matchStartOffset = 0
  let lastEndNode: Text | null = null
  let lastEndOffset = 0

  // Track if the last emitted unit was a space to coalesce whitespace across nodes
  let prevUnitWasSpace = false
  // Track if the last successfully matched needle char was a space
  let justMatchedSpace = false
  // Remember the previous non-space character (lowercased) for virtual-boundary space matching
  let prevNonSpaceChar: string | null = null

  const firstNeedleChar = needle[0]

  while (node) {
    const text = node.textContent || ''
    let i = 0

    while (i < text.length) {
      // Produce next normalized unit from the document stream
      let unitChar: string
      const unitStart = i
      let unitEnd = i + 1

      if (isWhitespace(text[i])) {
        // Consume full run of whitespace
        while (unitEnd < text.length && isWhitespace(text[unitEnd])) unitEnd++

        if (prevUnitWasSpace) {
          // Extend previous space unit if we are in the middle of a match
          if (justMatchedSpace && matchIdx > 0 && lastEndNode) {
            lastEndNode = node
            lastEndOffset = unitEnd
          }
          // Skip emitting another space unit
          i = unitEnd
          continue
        }
        unitChar = ' '
      } else {
        unitChar = text[unitStart].toLowerCase()
      }

      // Compare with current needle char
      const expected = needle[matchIdx]

      // Allow a virtual space match at cross-element boundaries when both sides are word chars
      if (
        expected === ' ' &&
        unitChar !== ' ' &&
        !prevUnitWasSpace &&
        prevNonSpaceChar &&
        /[\p{L}\p{N}]/u.test(prevNonSpaceChar) &&
        /[\p{L}\p{N}]/u.test(unitChar)
      ) {
        // Matched a virtual space without consuming any document character
        if (matchIdx === 0) {
          // Needle never starts with space due to normalization, so ignore
        } else {
          matchIdx++
          justMatchedSpace = true
          // Do not advance i; re-evaluate this same unit against the next expected char
          continue
        }
      }
      if (expected === unitChar) {
        // Start match
        if (matchIdx === 0) {
          matchStartNode = node
          matchStartOffset = unitStart
        }
        lastEndNode = node
        lastEndOffset = unitEnd
        matchIdx++
        justMatchedSpace = unitChar === ' '

        // If completed a match, create range
        if (matchIdx === needle.length) {
          const range = document.createRange()
          range.setStart(matchStartNode!, matchStartOffset)
          range.setEnd(lastEndNode!, lastEndOffset)
          ranges.push(range)

          // Reset for next potential match (non-overlapping search)
          matchIdx = 0
          matchStartNode = null
          justMatchedSpace = false
        }

        // Advance
        i = unitEnd
        prevUnitWasSpace = unitChar === ' '
        if (unitChar !== ' ') prevNonSpaceChar = unitChar
        continue
      }

      // Mismatch: reset state and consider current unit as new start if it matches first char
      matchIdx = 0
      matchStartNode = null
      justMatchedSpace = false

      if (firstNeedleChar === unitChar && unitChar !== ' ') {
        matchIdx = 1
        matchStartNode = node
        matchStartOffset = unitStart
        lastEndNode = node
        lastEndOffset = unitEnd
      }

      // Advance
      i = unitEnd
      prevUnitWasSpace = unitChar === ' '
      if (unitChar !== ' ') prevNonSpaceChar = unitChar
    }

    // Move to next node
    node = walker.nextNode() as Text | null
  }

  return ranges
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
