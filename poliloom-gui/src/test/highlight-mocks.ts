import { vi } from 'vitest'

// Mock the CSS Custom Highlight API for testing
global.CSS = {
  highlights: new Map(),
} as typeof CSS

global.Highlight = class MockHighlight {
  private ranges: Range[]

  constructor(...ranges: Range[]) {
    this.ranges = ranges
  }

  get size() {
    return this.ranges.length
  }

  values() {
    return this.ranges[Symbol.iterator]()
  }
} as unknown as typeof Highlight

vi.mock('@/hooks/useIframeHighlighting', () => ({
  useIframeAutoHighlight: () => ({
    isIframeLoaded: true,
    handleIframeLoad: vi.fn(),
    handleQuotesChange: vi.fn(),
  }),
}))
