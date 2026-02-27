import { Property, PropertyActionItem, CreatePropertyItem, PropertyType } from '@/types'

export function actionToEvaluation(actions: PropertyActionItem[], id: string): boolean | undefined {
  const action = actions.find((a) => a.action !== 'create' && a.id === id)
  if (!action) return undefined
  return action.action === 'accept'
}

export function applyAction(
  actions: PropertyActionItem[],
  id: string,
  action: 'accept' | 'reject' | 'remove',
): PropertyActionItem[] {
  if (action === 'remove') {
    return actions.filter((a) => !(a.action === 'create' && a.key === id))
  }

  const existing = actions.find((a) => a.action !== 'create' && a.id === id)

  if (existing) {
    if (existing.action === action) {
      // Toggle off: same action again removes it
      return actions.filter((a) => a !== existing)
    }
    // Replace: different action
    return actions.map((a) => (a === existing ? { ...a, action } : a)) as PropertyActionItem[]
  }

  // Add new action
  return [...actions, { action, id }]
}

export function createPropertyFromAction(action: CreatePropertyItem): Property {
  return {
    key: action.key,
    type: action.type as PropertyType,
    value: action.value,
    value_precision: action.value_precision,
    entity_id: action.entity_id,
    entity_name: action.entity_name,
    qualifiers: action.qualifiers,
    statement_id: null,
    sources: [],
    evaluation: true,
  }
}

export function stripCreateKeys(actions: PropertyActionItem[]): PropertyActionItem[] {
  return actions.map((a) => {
    if (a.action !== 'create') return a
    const { key, qualifiers, ...rest } = a
    return {
      ...rest,
      ...(qualifiers ? { qualifiers_json: qualifiers as Record<string, unknown> } : {}),
    } as PropertyActionItem
  })
}
