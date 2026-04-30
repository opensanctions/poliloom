'use client'

import { useEffect, useRef } from 'react'
import { useUser } from '@/contexts/UserContext'
import { useEntityCatalog } from '@/contexts/EntityCatalogContext'
import { detectBrowserLanguage } from '@/lib/detectBrowserLanguage'

// Fires once when GET /user returns null. The PATCH always runs (even with zero
// matches) so the user_settings row gets created and detection won't re-fire.
export function FirstLoginAutoDetect() {
  const { user, patch } = useUser()
  const { languages, loadingLanguages } = useEntityCatalog()
  const fired = useRef(false)

  useEffect(() => {
    if (fired.current) return
    if (user !== null) return
    if (loadingLanguages) return
    fired.current = true
    const detected = detectBrowserLanguage(languages)
    patch({ filters: { language: detected } })
  }, [user, loadingLanguages, languages, patch])

  return null
}
