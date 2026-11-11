'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Box } from '@/components/ui/Box'
import { Button } from '@/components/ui/Button'
import { Footer } from '@/components/ui/Footer'
import { Toggle } from '@/components/ui/Toggle'
import { MultiSelect, MultiSelectOption } from '@/components/entity/MultiSelect'
import { useSettings } from '@/contexts/SettingsContext'
import { useFilters } from '@/contexts/FilterContext'
import { useClaimPolitician } from '@/hooks/useClaimPolitician'
import { CountryResponse, LanguageResponse } from '@/types'
import { best_label } from '@/lib/labels'
import { useLabelLanguages } from '@/contexts/LabelLanguageContext'

interface CtaState {
  href?: string
  text: string
  disabled?: boolean
  onClick?: () => void
}

interface HomeContentProps {
  languages: LanguageResponse[]
  countries: CountryResponse[]
  initialEmptyResult?: boolean
}

export function HomeContent({
  languages,
  countries,
  initialEmptyResult = false,
}: HomeContentProps) {
  const router = useRouter()
  const { settings, patch } = useSettings()
  const { languageQids, countryQids, setLanguages, setCountries } = useFilters()
  const { claimAndNavigate, isClaiming } = useClaimPolitician()
  const [emptyResult, setEmptyResult] = useState(initialEmptyResult)
  const labelLanguages = useLabelLanguages()

  // Default tutorial completion to true when unauthenticated so we don't flash
  // a "Start Tutorial" CTA before redirect.
  const hasCompletedBasicTutorial = settings?.basic_tutorial_completed ?? true
  const hasCompletedAdvancedTutorial = settings?.advanced_tutorial_completed ?? true
  const isAdvancedMode = settings?.advanced_mode ?? false

  const needsTutorial = !hasCompletedBasicTutorial
  const needsAdvancedTutorial = isAdvancedMode && !hasCompletedAdvancedTutorial

  const startSession = async () => {
    const qid = await claimAndNavigate()
    if (qid === null) setEmptyResult(true)
  }

  let cta: CtaState = {
    text: 'Start Your Session',
    disabled: emptyResult || isClaiming,
    onClick: startSession,
  }
  if (needsTutorial) {
    cta = { href: '/tutorial', text: 'Start Tutorial' }
  } else if (needsAdvancedTutorial) {
    cta = { href: '/tutorial', text: 'Start Advanced Tutorial' }
  }

  const changeLanguages = (qids: string[]) => {
    setEmptyResult(false)
    if (emptyResult) router.replace('/')
    setLanguages(qids)
  }

  const changeCountries = (qids: string[]) => {
    setEmptyResult(false)
    if (emptyResult) router.replace('/')
    setCountries(qids)
  }

  const languageOptions: MultiSelectOption[] = languages.map((lang) => ({
    value: lang.wikidata_id,
    label: best_label(lang.terms, labelLanguages, lang.wikidata_id),
    count: lang.sources_count,
  }))

  const countryOptions: MultiSelectOption[] = countries.map((country) => ({
    value: country.wikidata_id,
    label: best_label(country.terms, labelLanguages, country.wikidata_id),
    count: country.citizenships_count,
  }))

  return (
    <main className="min-h-0 overflow-y-auto flex flex-col">
      {/* Filters Section */}
      <div className="flex-1 max-w-6xl mx-auto px-6 pt-12 w-full">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-foreground mb-4">Configure Your Session</h1>
          <p className="text-lg text-foreground-tertiary">
            Pick your focus, then work through politicians at your own pace.
          </p>
        </div>

        <div className="space-y-6">
          <MultiSelect
            title="Which countries are you interested in?"
            description="We'll show you politicians with citizenship from these countries"
            icon="🌍"
            options={countryOptions}
            selected={countryQids}
            onChange={changeCountries}
          />

          <MultiSelect
            title="What languages can you read?"
            description="We'll show you politicians with source documents in these languages"
            icon="🌐"
            options={languageOptions}
            selected={languageQids}
            onChange={changeLanguages}
            minimumSelections={1}
          />
        </div>

        {/* CTA Section */}
        <Box className="mt-12 p-8">
          <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h3 className="text-lg font-semibold text-foreground mb-2">
                {emptyResult ? 'No politicians found' : 'Ready to start?'}
              </h3>
              <p className="text-foreground-tertiary">
                {emptyResult
                  ? 'No politicians found for your current filters. Try different filters to continue contributing.'
                  : 'Your filters are set. Begin reviewing politicians that match your criteria.'}
              </p>
            </div>
            <Button
              href={cta.href}
              onClick={cta.onClick}
              disabled={cta.disabled}
              size="xlarge"
              className="shrink-0"
            >
              {cta.text}
            </Button>
          </div>

          {/* Advanced Mode Toggle */}
          <div className="mt-6 pt-6 border-t border-border-muted">
            <label className="flex items-center gap-3 text-sm text-foreground-tertiary cursor-pointer">
              <Toggle
                checked={isAdvancedMode}
                onChange={(e) => patch({ advanced_mode: e.target.checked })}
              />
              <span>
                Advanced mode{' '}
                <span className="text-foreground-subtle">
                  — unlocks an additional tutorial covering proposed edits to existing statements
                </span>
              </span>
            </label>
          </div>
        </Box>
      </div>

      <Footer />
    </main>
  )
}
