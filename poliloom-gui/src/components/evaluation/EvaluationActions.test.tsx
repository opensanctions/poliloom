import { render, screen } from '@testing-library/react'
import { EvaluationActions } from './EvaluationActions'

describe('EvaluationActions', () => {
  describe('Wikidata statements', () => {
    it('hides Deprecate button when not in advanced mode, even with source visible', () => {
      render(
        <EvaluationActions
          statementId="stmt-1"
          isWikidataStatement={true}
          isUserAdded={false}
          isAccepted={null}
          isSourceVisible={true}
          isAdvancedMode={false}
          onAction={vi.fn()}
        />,
      )

      expect(screen.queryByRole('button', { name: /Deprecate/ })).not.toBeInTheDocument()
      expect(screen.getByText('Existing data')).toBeInTheDocument()
    })

    it('shows Deprecate button in advanced mode', () => {
      render(
        <EvaluationActions
          statementId="stmt-1"
          isWikidataStatement={true}
          isUserAdded={false}
          isAccepted={null}
          isSourceVisible={true}
          isAdvancedMode={true}
          onAction={vi.fn()}
        />,
      )

      expect(screen.getByRole('button', { name: /Deprecate/ })).toBeInTheDocument()
    })
  })

  describe('new data statements', () => {
    it('shows Accept/Reject buttons when source is visible', () => {
      render(
        <EvaluationActions
          statementId="stmt-1"
          isWikidataStatement={false}
          isUserAdded={false}
          isAccepted={null}
          isSourceVisible={true}
          isAdvancedMode={false}
          onAction={vi.fn()}
        />,
      )

      expect(screen.getByRole('button', { name: /Accept/ })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Reject/ })).toBeInTheDocument()
    })

    it('hides buttons when source is not visible', () => {
      render(
        <EvaluationActions
          statementId="stmt-1"
          isWikidataStatement={false}
          isUserAdded={false}
          isAccepted={null}
          isSourceVisible={false}
          isAdvancedMode={false}
          onAction={vi.fn()}
        />,
      )

      expect(screen.queryByRole('button', { name: /Accept/ })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Reject/ })).not.toBeInTheDocument()
      expect(screen.getByText('View source to evaluate')).toBeInTheDocument()
    })
  })

  describe('user-added properties', () => {
    it('shows Remove button instead of Reject and hides Accept', () => {
      render(
        <EvaluationActions
          statementId="new-123"
          isWikidataStatement={false}
          isUserAdded={true}
          isAccepted={true}
          isSourceVisible={true}
          isAdvancedMode={false}
          onAction={vi.fn()}
        />,
      )

      expect(screen.getByRole('button', { name: /Remove/ })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Reject/ })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Accept/ })).not.toBeInTheDocument()
    })
  })
})
