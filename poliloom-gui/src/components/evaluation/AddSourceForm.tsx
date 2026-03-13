'use client'

import { useState } from 'react'
import { ArchivedPageResponse } from '@/types'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'

interface AddSourceFormProps {
  politicianQid: string
  onAdd: (source: ArchivedPageResponse) => void
  onCancel: () => void
}

export function AddSourceForm({ politicianQid, onAdd, onCancel }: AddSourceFormProps) {
  const [url, setUrl] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const isValidUrl = (() => {
    try {
      new URL(url)
      return true
    } catch {
      return false
    }
  })()

  const handleSubmit = async () => {
    if (!isValidUrl) return

    setIsSubmitting(true)
    setError(null)

    try {
      const response = await fetch(`/api/politicians/${politicianQid}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      })

      if (!response.ok) {
        const data = await response.json().catch(() => null)
        throw new Error(data?.detail || `Failed to add source: ${response.statusText}`)
      }

      const source: ArchivedPageResponse = await response.json()
      onAdd(source)
      setIsSubmitting(false)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to add source')
      setIsSubmitting(false)
    }
  }

  return (
    <div className="border border-border rounded-lg px-6 py-5 space-y-3">
      <Input
        placeholder="https://..."
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        disabled={isSubmitting}
        error={error ?? undefined}
      />
      <div className="flex gap-2">
        <Button size="small" onClick={handleSubmit} disabled={!isValidUrl || isSubmitting}>
          {isSubmitting ? 'Adding...' : '+ Add'}
        </Button>
        <Button size="small" variant="secondary" onClick={onCancel} disabled={isSubmitting}>
          Cancel
        </Button>
      </div>
    </div>
  )
}
