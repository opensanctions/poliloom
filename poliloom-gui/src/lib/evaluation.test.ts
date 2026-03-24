import { describe, it, expect } from 'vitest'
import { actionToEvaluation, applyAction, createPropertyFromAction } from './evaluation'
import type { PropertyActionItem, CreatePropertyItem } from '@/types'
import { PropertyType } from '@/types'

describe('actionToEvaluation', () => {
  it('returns undefined when no action exists for the id', () => {
    expect(actionToEvaluation([], 'prop-1')).toBeUndefined()
  })

  it('returns true for an accepted property', () => {
    const actions: PropertyActionItem[] = [{ action: 'accept', id: 'prop-1' }]
    expect(actionToEvaluation(actions, 'prop-1')).toBe(true)
  })

  it('returns false for a rejected property', () => {
    const actions: PropertyActionItem[] = [{ action: 'reject', id: 'prop-1' }]
    expect(actionToEvaluation(actions, 'prop-1')).toBe(false)
  })

  it('ignores create actions', () => {
    const actions: PropertyActionItem[] = [
      {
        action: 'create',
        id: 'prop-1',
        type: 'P569',
        value: '+2000-01-01T00:00:00Z',
      },
    ]
    expect(actionToEvaluation(actions, 'prop-1')).toBeUndefined()
  })

  it('finds the correct action among multiple', () => {
    const actions: PropertyActionItem[] = [
      { action: 'accept', id: 'prop-1' },
      { action: 'reject', id: 'prop-2' },
      { action: 'accept', id: 'prop-3' },
    ]
    expect(actionToEvaluation(actions, 'prop-2')).toBe(false)
  })
})

describe('applyAction', () => {
  it('adds a new accept action', () => {
    const result = applyAction([], 'prop-1', 'accept')
    expect(result).toEqual([{ action: 'accept', id: 'prop-1' }])
  })

  it('adds a new reject action', () => {
    const result = applyAction([], 'prop-1', 'reject')
    expect(result).toEqual([{ action: 'reject', id: 'prop-1' }])
  })

  it('toggles off when same action is applied again', () => {
    const actions: PropertyActionItem[] = [{ action: 'accept', id: 'prop-1' }]
    const result = applyAction(actions, 'prop-1', 'accept')
    expect(result).toEqual([])
  })

  it('replaces action when different action is applied', () => {
    const actions: PropertyActionItem[] = [{ action: 'accept', id: 'prop-1' }]
    const result = applyAction(actions, 'prop-1', 'reject')
    expect(result).toEqual([{ action: 'reject', id: 'prop-1' }])
  })

  it('removes a create action when rejecting it', () => {
    const actions: PropertyActionItem[] = [
      {
        action: 'create',
        id: 'new-1',
        type: 'P569',
        value: '+2000-01-01T00:00:00Z',
      },
    ]
    const result = applyAction(actions, 'new-1', 'reject')
    expect(result).toEqual([])
  })

  it('preserves other actions when modifying one', () => {
    const actions: PropertyActionItem[] = [
      { action: 'accept', id: 'prop-1' },
      { action: 'reject', id: 'prop-2' },
    ]
    const result = applyAction(actions, 'prop-1', 'reject')
    expect(result).toEqual([
      { action: 'reject', id: 'prop-1' },
      { action: 'reject', id: 'prop-2' },
    ])
  })

  it('does not mutate the original array', () => {
    const actions: PropertyActionItem[] = [{ action: 'accept', id: 'prop-1' }]
    const result = applyAction(actions, 'prop-1', 'reject')
    expect(actions).toEqual([{ action: 'accept', id: 'prop-1' }])
    expect(result).not.toBe(actions)
  })
})

describe('createPropertyFromAction', () => {
  it('creates a property from a date create action', () => {
    const action: CreatePropertyItem = {
      action: 'create',
      id: 'new-1',
      type: 'P569',
      value: '+1990-05-15T00:00:00Z',
      value_precision: 11,
    }

    const property = createPropertyFromAction(action)

    expect(property).toEqual({
      id: 'new-1',
      type: PropertyType.P569,
      value: '+1990-05-15T00:00:00Z',
      value_precision: 11,
      entity_id: undefined,
      entity_name: undefined,
      qualifiers: undefined,
      statement_id: null,
      sources: [],
      userAdded: true,
      evaluation: true,
    })
  })

  it('creates a property from an entity create action', () => {
    const action: CreatePropertyItem = {
      action: 'create',
      id: 'new-2',
      type: 'P19',
      entity_id: 'Q1234',
      entity_name: 'Berlin',
    }

    const property = createPropertyFromAction(action)

    expect(property.type).toBe(PropertyType.P19)
    expect(property.entity_id).toBe('Q1234')
    expect(property.entity_name).toBe('Berlin')
    expect(property.userAdded).toBe(true)
    expect(property.sources).toEqual([])
  })

  it('creates a property from a position create action with qualifiers', () => {
    const qualifiers = {
      P580: [{ datavalue: { value: { time: '+2020-01-01T00:00:00Z', precision: 11 } } }],
    }
    const action: CreatePropertyItem = {
      action: 'create',
      id: 'new-3',
      type: 'P39',
      entity_id: 'Q5678',
      entity_name: 'Mayor',
      qualifiers,
    }

    const property = createPropertyFromAction(action)

    expect(property.type).toBe(PropertyType.P39)
    expect(property.qualifiers).toEqual(qualifiers)
  })
})
