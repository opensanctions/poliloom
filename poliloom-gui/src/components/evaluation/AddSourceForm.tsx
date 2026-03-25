'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'

interface AddSourceFormProps {
  onSubmit: (url: string) => Promise<void>
}

export function AddSourceForm({ onSubmit }: AddSourceFormProps) {
  const [isOpen, setIsOpen] = useState(false)
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
      await onSubmit(url)
      setUrl('')
      setIsOpen(false)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to add source')
    } finally {
      setIsSubmitting(false)
    }
  }

  if (!isOpen) {
    return (
      <Button variant="secondary" size="small" onClick={() => setIsOpen(true)}>
        + Add Source
      </Button>
    )
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
        <Button
          size="small"
          variant="secondary"
          onClick={() => setIsOpen(false)}
          disabled={isSubmitting}
        >
          Cancel
        </Button>
      </div>
    </div>
  )
}
