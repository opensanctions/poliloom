import { TermMaps } from '@/types'
import type { SectionType } from '@/lib/actions'
import { best_label } from '@/lib/labels'
import { EntityLink } from '@/components/ui/EntityLink'
import { useLabelLanguages } from '@/contexts/LabelLanguageContext'

interface GroupTitleProps {
  sectionType: SectionType
  /** Entity QID for entity sections, property id for date sections. */
  groupKey: string
  terms: TermMaps | null
}

export function GroupTitle({ sectionType, groupKey, terms }: GroupTitleProps) {
  const labelLanguages = useLabelLanguages()
  if (sectionType === 'date') {
    return groupKey === 'P569' ? <>Birth Date</> : <>Death Date</>
  }
  return <EntityLink entityId={groupKey} entityName={best_label(terms, labelLanguages, groupKey)} />
}
