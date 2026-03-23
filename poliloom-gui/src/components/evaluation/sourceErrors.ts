const errorDescriptions: Record<string, string> = {
  FETCH_ERROR: 'Fetch failed',
  TIMEOUT: 'Timed out',
  NO_RESPONSE: 'No response',
  BROWSER_ERROR: 'Browser error',
  INVALID_CONTENT: 'No readable content',
  PIPELINE_ERROR: 'Processing error',
}

export function formatSourceError(error: string, httpStatusCode?: number | null): string {
  const description = errorDescriptions[error] ?? error
  if (error === 'FETCH_ERROR' && httpStatusCode) {
    return `${description} (HTTP ${httpStatusCode})`
  }
  return description
}
