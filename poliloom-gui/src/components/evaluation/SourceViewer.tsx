import { RefObject } from 'react'

interface SourceViewerProps {
  pageId: string
  apiBasePath?: string
  iframeRef?: RefObject<HTMLIFrameElement | null>
  onLoad?: () => void
}

export function SourceViewer({
  pageId,
  apiBasePath = '/api/sources',
  iframeRef,
  onLoad,
}: SourceViewerProps) {
  return (
    <iframe
      ref={iframeRef}
      src={`${apiBasePath}/${pageId}/html`}
      className="w-full h-full border-0"
      title="Archived Page"
      sandbox="allow-scripts allow-same-origin"
      onLoad={onLoad}
    />
  )
}
