import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import CreatePage from './page'
import { Property, PropertyType, Politician } from '@/types'
import React from 'react'

// Mock components
vi.mock('@/components/layout/Header', () => ({
  Header: () => <div data-testid="header">Header</div>,
}))

vi.mock('@/components/ui/Button', () => ({
  Button: ({
    children,
    onClick,
    disabled,
    ...props
  }: React.ButtonHTMLAttributes<HTMLButtonElement>) => (
    <button onClick={onClick} disabled={disabled} {...props}>
      {children}
    </button>
  ),
}))

vi.mock('@/components/evaluation/PropertiesEvaluation', () => ({
  PropertiesEvaluation: ({
    properties,
    evaluations,
    onAction,
  }: {
    properties: Property[]
    evaluations: Map<string, boolean>
    onAction: (propertyId: string, action: 'accept' | 'reject') => void
  }) => (
    <div data-testid="properties-evaluation">
      {properties.map((prop: Property) => (
        <div key={prop.key} data-testid={`property-${prop.key}`}>
          <span>{prop.type}</span>
          <button data-testid={`accept-${prop.key}`} onClick={() => onAction(prop.key, 'accept')}>
            Accept
          </button>
          <button data-testid={`reject-${prop.key}`} onClick={() => onAction(prop.key, 'reject')}>
            Reject
          </button>
          <span data-testid={`evaluation-${prop.key}`}>
            {evaluations.get(prop.key) === true
              ? 'accepted'
              : evaluations.get(prop.key) === false
                ? 'rejected'
                : 'pending'}
          </span>
        </div>
      ))}
    </div>
  ),
}))

vi.mock('@/components/entity/AddPropertyForm', () => ({
  AddPropertyForm: ({ onAddProperty }: { onAddProperty: (property: Property) => void }) => (
    <div data-testid="add-property-form">
      <button
        data-testid="add-manual-property"
        onClick={() =>
          onAddProperty({
            key: 'manual-1',
            type: PropertyType.P569,
            value: '+1980-01-01T00:00:00Z',
            value_precision: 11,
            references: [{ P854: [{ datavalue: { value: 'https://example.com' } }] }],
            sources: [],
          })
        }
      >
        Add Manual Property
      </button>
    </div>
  ),
}))

vi.mock('@/components/entity/EntitySelector', () => ({
  EntitySelector: ({
    onSelect,
    onCreateNew,
  }: {
    onSelect: (politician: Politician) => void
    onCreateNew: (name: string) => void
  }) => (
    <div data-testid="entity-selector">
      <button
        data-testid="select-existing"
        onClick={() =>
          onSelect({
            id: 'existing-123',
            name: 'John Doe',
            wikidata_id: 'Q123',
            properties: [
              {
                id: 'backend-1',
                key: 'backend-1',
                type: PropertyType.P569,
                value: '+1970-01-01T00:00:00Z',
                value_precision: 11,
              },
            ],
          } as Politician)
        }
      >
        Select Existing
      </button>
      <button data-testid="create-new" onClick={() => onCreateNew('Jane Doe')}>
        Create New
      </button>
    </div>
  ),
}))

// Mock fetch globally
global.fetch = vi.fn()

describe('CreatePage Submit Functionality', () => {
  const user = userEvent.setup()

  beforeEach(() => {
    vi.clearAllMocks()
    // Mock window.alert
    vi.spyOn(window, 'alert').mockImplementation(() => {})
  })

  describe('New politician creation', () => {
    it('should create a new politician with manually added confirmed properties', async () => {
      const mockResponse = {
        success: true,
        message: 'Successfully created politician',
        politicians: [
          {
            id: 'new-politician-id',
            name: 'Jane Doe',
            wikidata_id: null,
            properties: [
              {
                id: 'property-id-1',
                type: PropertyType.P569,
                value: '+1980-01-01T00:00:00Z',
                value_precision: 11,
              },
            ],
          },
        ],
      }

      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      } as Response)

      render(<CreatePage />)

      // Create a new politician
      const createNewButton = screen.getByTestId('create-new')
      await user.click(createNewButton)

      // Add a manual property
      const addPropertyButton = screen.getByTestId('add-manual-property')
      await user.click(addPropertyButton)

      // Submit
      const submitButton = screen.getByText('Create Politician')
      await user.click(submitButton)

      // Verify API call
      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          '/api/politicians',
          expect.objectContaining({
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: expect.stringContaining('Jane Doe'),
          }),
        )
      })

      // Verify success message
      expect(window.alert).toHaveBeenCalledWith('Successfully created Jane Doe')

      // Verify form is cleared
      await waitFor(() => {
        expect(screen.queryByTestId('properties-evaluation')).not.toBeInTheDocument()
      })
    })

    it('should show validation error when no properties are confirmed for new politician', async () => {
      render(<CreatePage />)

      // Create a new politician without adding properties
      const createNewButton = screen.getByTestId('create-new')
      await user.click(createNewButton)

      // Try to submit without properties
      const submitButton = screen.getByText('Create Politician')
      await user.click(submitButton)

      // Verify validation error
      expect(window.alert).toHaveBeenCalledWith(
        'Please add at least one property or evaluate existing properties',
      )
      expect(global.fetch).not.toHaveBeenCalled()
    })
  })

  describe('Existing politician - adding properties', () => {
    it('should add new properties to existing politician', async () => {
      const mockResponse = {
        success: true,
        message: 'Successfully added properties',
        properties: [
          {
            id: 'new-property-id',
            type: PropertyType.P569,
            value: '+1980-01-01T00:00:00Z',
            value_precision: 11,
          },
        ],
      }

      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      } as Response)

      render(<CreatePage />)

      // Select an existing politician
      const selectExistingButton = screen.getByTestId('select-existing')
      await user.click(selectExistingButton)

      // Add a manual property
      const addPropertyButton = screen.getByTestId('add-manual-property')
      await user.click(addPropertyButton)

      // Submit
      const submitButton = screen.getByText('Update Politician')
      await user.click(submitButton)

      // Verify API call
      await waitFor(() => {
        expect(fetch).toHaveBeenCalledWith(
          '/api/politicians/existing-123/properties',
          expect.objectContaining({
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
          }),
        )
      })

      // Verify success message
      expect(window.alert).toHaveBeenCalledWith('Successfully updated John Doe')
    })
  })

  describe('Existing politician - evaluating properties', () => {
    it('should submit evaluations for extracted properties', async () => {
      const mockResponse = {
        success: true,
        message: 'Successfully processed evaluations',
        evaluations: [],
        errors: [],
      }

      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      } as Response)

      render(<CreatePage />)

      // Select an existing politician with backend properties
      const selectExistingButton = screen.getByTestId('select-existing')
      await user.click(selectExistingButton)

      // Accept the backend property
      const acceptButton = screen.getByTestId('accept-backend-1')
      await user.click(acceptButton)

      // Verify property is marked as accepted
      expect(screen.getByTestId('evaluation-backend-1')).toHaveTextContent('accepted')

      // Submit
      const submitButton = screen.getByText('Update Politician')
      await user.click(submitButton)

      // Verify API call
      await waitFor(() => {
        expect(fetch).toHaveBeenCalledWith(
          '/api/evaluations',
          expect.objectContaining({
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              evaluations: [
                {
                  id: 'backend-1',
                  is_confirmed: true,
                },
              ],
            }),
          }),
        )
      })

      // Verify success message
      expect(window.alert).toHaveBeenCalledWith('Successfully updated John Doe')
    })

    it('should handle reject evaluations', async () => {
      const mockResponse = {
        success: true,
        message: 'Successfully processed evaluations',
        evaluations: [],
        errors: [],
      }

      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      } as Response)

      render(<CreatePage />)

      // Select an existing politician with backend properties
      const selectExistingButton = screen.getByTestId('select-existing')
      await user.click(selectExistingButton)

      // Reject the backend property
      const rejectButton = screen.getByTestId('reject-backend-1')
      await user.click(rejectButton)

      // Verify property is marked as rejected
      expect(screen.getByTestId('evaluation-backend-1')).toHaveTextContent('rejected')

      // Submit
      const submitButton = screen.getByText('Update Politician')
      await user.click(submitButton)

      // Verify API call
      await waitFor(() => {
        expect(fetch).toHaveBeenCalledWith(
          '/api/evaluations',
          expect.objectContaining({
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              evaluations: [
                {
                  id: 'backend-1',
                  is_confirmed: false,
                },
              ],
            }),
          }),
        )
      })

      // Verify success message
      expect(window.alert).toHaveBeenCalledWith('Successfully updated John Doe')
    })
  })

  describe('Combined flow - adding and evaluating', () => {
    it('should handle both adding properties and evaluating properties in parallel', async () => {
      const mockPropertyResponse = {
        success: true,
        message: 'Successfully added properties',
        properties: [],
      }

      const mockEvaluationResponse = {
        success: true,
        message: 'Successfully processed evaluations',
        evaluations: [],
        errors: [],
      }

      // Mock both API calls
      vi.mocked(fetch)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockPropertyResponse,
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockEvaluationResponse,
        } as Response)

      render(<CreatePage />)

      // Select an existing politician with backend properties
      const selectExistingButton = screen.getByTestId('select-existing')
      await user.click(selectExistingButton)

      // Add a manual property
      const addPropertyButton = screen.getByTestId('add-manual-property')
      await user.click(addPropertyButton)

      // Accept the backend property
      const acceptButton = screen.getByTestId('accept-backend-1')
      await user.click(acceptButton)

      // Submit
      const submitButton = screen.getByText('Update Politician')
      await user.click(submitButton)

      // Verify both API calls were made
      await waitFor(() => {
        expect(fetch).toHaveBeenCalledTimes(2)
        expect(fetch).toHaveBeenCalledWith(
          '/api/politicians/existing-123/properties',
          expect.any(Object),
        )
        expect(fetch).toHaveBeenCalledWith('/api/evaluations', expect.any(Object))
      })

      // Verify success message
      expect(window.alert).toHaveBeenCalledWith('Successfully updated John Doe')
    })
  })

  describe('Error handling', () => {
    it('should display API errors to user', async () => {
      vi.mocked(fetch).mockResolvedValueOnce({
        ok: false,
        statusText: 'Internal Server Error',
      } as Response)

      // Mock console.error to suppress expected error output
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      render(<CreatePage />)

      // Create a new politician and add property
      const createNewButton = screen.getByTestId('create-new')
      await user.click(createNewButton)

      const addPropertyButton = screen.getByTestId('add-manual-property')
      await user.click(addPropertyButton)

      // Submit
      const submitButton = screen.getByText('Create Politician')
      await user.click(submitButton)

      // Verify error message
      await waitFor(() => {
        expect(window.alert).toHaveBeenCalledWith(
          expect.stringContaining('Failed to create politician'),
        )
      })

      // Verify error was logged
      expect(consoleErrorSpy).toHaveBeenCalledWith('Error submitting:', expect.any(Error))

      consoleErrorSpy.mockRestore()
    })

    it('should display validation errors from API response', async () => {
      const mockResponse = {
        success: false,
        message: 'Validation failed',
        errors: ['Property value is invalid', 'Missing required field'],
      }

      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      } as Response)

      render(<CreatePage />)

      // Create a new politician and add property
      const createNewButton = screen.getByTestId('create-new')
      await user.click(createNewButton)

      const addPropertyButton = screen.getByTestId('add-manual-property')
      await user.click(addPropertyButton)

      // Submit
      const submitButton = screen.getByText('Create Politician')
      await user.click(submitButton)

      // Verify error message displays validation errors
      await waitFor(() => {
        expect(window.alert).toHaveBeenCalledWith(
          expect.stringContaining('Property value is invalid'),
        )
        expect(window.alert).toHaveBeenCalledWith(expect.stringContaining('Missing required field'))
      })
    })
  })

  describe('Property filtering logic', () => {
    it('should only submit manually added properties that are confirmed', async () => {
      const mockResponse = {
        success: true,
        message: 'Success',
        politicians: [],
      }

      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      } as Response)

      render(<CreatePage />)

      // Create a new politician
      const createNewButton = screen.getByTestId('create-new')
      await user.click(createNewButton)

      // Add a manual property (auto-confirmed)
      const addPropertyButton = screen.getByTestId('add-manual-property')
      await user.click(addPropertyButton)

      // Submit
      const submitButton = screen.getByText('Create Politician')
      await user.click(submitButton)

      // Verify only confirmed properties are sent
      await waitFor(() => {
        const callArgs = vi.mocked(fetch).mock.calls[0]
        const requestInit = callArgs[1] as RequestInit
        const body = JSON.parse(requestInit.body as string)
        expect(body.politicians[0].properties).toHaveLength(1)
        expect(body.politicians[0].properties[0].type).toBe(PropertyType.P569)
      })
    })

    it('should only submit backend properties that have been evaluated', async () => {
      const mockResponse = {
        success: true,
        message: 'Success',
        evaluations: [],
        errors: [],
      }

      vi.mocked(fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      } as Response)

      render(<CreatePage />)

      // Select an existing politician with backend properties
      const selectExistingButton = screen.getByTestId('select-existing')
      await user.click(selectExistingButton)

      // Accept the backend property
      const acceptButton = screen.getByTestId('accept-backend-1')
      await user.click(acceptButton)

      // Submit
      const submitButton = screen.getByText('Update Politician')
      await user.click(submitButton)

      // Verify only evaluated properties are sent
      await waitFor(() => {
        const callArgs = vi.mocked(fetch).mock.calls[0]
        const requestInit = callArgs[1] as RequestInit
        const body = JSON.parse(requestInit.body as string)
        expect(body.evaluations).toHaveLength(1)
        expect(body.evaluations[0].id).toBe('backend-1')
        expect(body.evaluations[0].is_confirmed).toBe(true)
      })
    })
  })
})
