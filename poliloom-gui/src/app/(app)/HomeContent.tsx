'use client'

import { useMemo } from 'react'
import { Box } from '@/components/ui/Box'
import { Button } from '@/components/ui/Button'
import { Footer } from '@/components/ui/Footer'
import { Toggle } from '@/components/ui/Toggle'
import { MultiSelect, MultiSelectOption } from '@/components/entity/MultiSelect'
import { useSettings } from '@/contexts/SettingsContext'
import { useFilters } from '@/contexts/FilterContext'
import { useEvaluationSession } from '@/contexts/EvaluationSessionContext'
import { useNextPoliticianContext } from '@/contexts/NextPoliticianContext'
import { CountryResponse, LanguageResponse } from '@/types'

interface CtaState {
  href?: string
  text: string
  disabled?: boolean
  startSession?: boolean
}

interface HomeContentProps {
  languages: LanguageResponse[]
  countries: CountryResponse[]
}

export function HomeContent({ languages, countries }: HomeContentProps) {
  const { settings, patch } = useSettings()
  const { languageQids, countryQids, setLanguages, setCountries } = useFilters()
  const { startSession } = useEvaluationSession()
  const {
    nextHref,
    politicianReady,
    allCaughtUp,
    loading: loadingNext,
  } = useNextPoliticianContext()

  // Default tutorial completion to true when unauthenticated so we don't flash
  // a "Start Tutorial" CTA before redirect.
  const hasCompletedBasicTutorial = settings?.basic_tutorial_completed ?? true
  const hasCompletedAdvancedTutorial = settings?.advanced_tutorial_completed ?? true
  const isAdvancedMode = settings?.advanced_mode ?? false

  const needsTutorial = !hasCompletedBasicTutorial
  const needsAdvancedTutorial = isAdvancedMode && !hasCompletedAdvancedTutorial

  const cta = useMemo<CtaState>(() => {
    if (needsTutorial) return { href: '/tutorial', text: 'Start Tutorial' }
    if (needsAdvancedTutorial) return { href: '/tutorial', text: 'Start Advanced Tutorial' }
    if (loadingNext) return { text: 'Start Your Session', disabled: true }
    if (!allCaughtUp) return { href: nextHref, text: 'Start Your Session', startSession: true }
    return { text: 'Start Your Session', disabled: true }
  }, [needsTutorial, needsAdvancedTutorial, loadingNext, nextHref, allCaughtUp])

  const languageOptions: MultiSelectOption[] = languages.map((lang) => ({
    value: lang.wikidata_id,
    label: lang.name,
    count: lang.sources_count,
  }))

  const countryOptions: MultiSelectOption[] = countries.map((country) => ({
    value: country.wikidata_id,
    label: country.name,
    count: country.citizenships_count,
  }))

  return (
    <main className="min-h-0 overflow-y-auto flex flex-col">
      {/* Filters Section */}
      <div className="flex-1 max-w-6xl mx-auto px-6 pt-12 w-full">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-foreground mb-4">Configure Your Session</h1>
          <p className="text-lg text-foreground-tertiary">
            Pick your focus, then work through a batch of politicians at your own pace.
          </p>
        </div>

        <div className="space-y-6">
          <MultiSelect
            title="Which countries are you interested in?"
            description="We'll show you politicians with citizenship from these countries"
            icon="🌍"
            options={countryOptions}
            selected={countryQids}
            onChange={setCountries}
          />

          <MultiSelect
            title="What languages can you read?"
            description="We'll show you politicians with source documents in these languages"
            icon="🌐"
            options={languageOptions}
            selected={languageQids}
            onChange={setLanguages}
            minimumSelections={1}
          />
        </div>

        {/* CTA Section */}
        <Box className="mt-12 p-8">
          <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h3 className="text-lg font-semibold text-foreground mb-2">
                {allCaughtUp ? 'All Caught Up!' : 'Ready to start?'}
              </h3>
              <p className="text-foreground-tertiary">
                {allCaughtUp
                  ? 'No more politicians to evaluate for your current filters. Try different filters to continue contributing.'
                  : !politicianReady && !loadingNext
                    ? "Our AI is reading Wikipedia so you don't have to. Hang tight!"
                    : 'Your filters are set. Begin evaluating politicians that match your criteria.'}
              </p>
            </div>
            <Button
              href={cta.href}
              disabled={cta.disabled}
              size="xlarge"
              className="shrink-0"
              onClick={cta.startSession ? () => startSession() : undefined}
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
                  — enables creating new and deprecating existing Wikidata statements
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
