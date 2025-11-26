import { render, screen, fireEvent } from '@testing-library/react'
import { EvaluationItem } from './EvaluationItem'
import { vi } from 'vitest'

describe('EvaluationItem', () => {
  it('renders title and children', () => {
    render(
      <EvaluationItem title="Test Title">
        <div>Test content</div>
      </EvaluationItem>,
    )

    expect(screen.getByText('Test Title')).toBeInTheDocument()
    expect(screen.getByText('Test content')).toBeInTheDocument()
  })

  it('calls onHover when mouse enters component', () => {
    const onHover = vi.fn()

    render(
      <EvaluationItem title="Test Title" onHover={onHover}>
        <div>Content</div>
      </EvaluationItem>,
    )

    const container = screen.getByText('Test Title').closest('div')
    fireEvent.mouseEnter(container!)

    expect(onHover).toHaveBeenCalledTimes(1)
  })

  it('does not call onHover when callback not provided', () => {
    render(
      <EvaluationItem title="Test Title">
        <div>Content</div>
      </EvaluationItem>,
    )

    const container = screen.getByText('Test Title').closest('div')
    fireEvent.mouseEnter(container!)

    // Should not throw error
  })
})
