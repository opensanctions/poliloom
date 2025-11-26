import { RefObject } from 'react'

interface ArchivedPageViewerProps {
  pageId: string
  apiBasePath?: string
  iframeRef?: RefObject<HTMLIFrameElement | null>
  onLoad?: () => void
}

export function ArchivedPageViewer({
  pageId,
  apiBasePath = '/api/archived-pages',
  iframeRef,
  onLoad,
}: ArchivedPageViewerProps) {
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
