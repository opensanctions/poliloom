import { render, screen, fireEvent } from '@testing-library/react'
import {
  DatePrecisionPicker,
  formatWikidataDate,
  inferPrecision,
  hasYear,
} from './DatePrecisionPicker'

describe('inferPrecision', () => {
  it('returns 11 (day) when year, month, and day are all set', () => {
    expect(inferPrecision({ year: '1990', month: '05', day: '15' })).toBe(11)
  })

  it('returns 10 (month) when day is empty', () => {
    expect(inferPrecision({ year: '1990', month: '05', day: '' })).toBe(10)
  })

  it('returns 9 (year) when month is empty', () => {
    expect(inferPrecision({ year: '1990', month: '', day: '' })).toBe(9)
  })

  it('returns 9 (year) when month is empty even if day is set', () => {
    expect(inferPrecision({ year: '1990', month: '', day: '15' })).toBe(9)
  })
})

describe('formatWikidataDate', () => {
  it('formats full date', () => {
    expect(formatWikidataDate({ year: '1990', month: '05', day: '15' })).toBe(
      '+1990-05-15T00:00:00Z',
    )
  })

  it('zeroes day when empty', () => {
    expect(formatWikidataDate({ year: '1990', month: '05', day: '' })).toBe('+1990-05-00T00:00:00Z')
  })

  it('zeroes month and day when both empty', () => {
    expect(formatWikidataDate({ year: '1990', month: '', day: '' })).toBe('+1990-00-00T00:00:00Z')
  })
})

describe('hasYear', () => {
  it('returns true when year is set', () => {
    expect(hasYear({ year: '1990', month: '', day: '' })).toBe(true)
  })

  it('returns false when year is empty', () => {
    expect(hasYear({ year: '', month: '', day: '' })).toBe(false)
  })
})

describe('DatePrecisionPicker', () => {
  const emptyValue = { year: '', month: '', day: '' }
  const defaultProps = {
    value: emptyValue,
    onChange: vi.fn(),
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders year, month, and day inputs', () => {
    render(<DatePrecisionPicker {...defaultProps} />)

    expect(screen.getByPlaceholderText('Year')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Month')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Day')).toBeInTheDocument()
  })

  it('renders label when provided', () => {
    render(<DatePrecisionPicker {...defaultProps} label="Start" />)

    expect(screen.getByText('Start')).toBeInTheDocument()
  })

  it('does not render label when not provided', () => {
    render(<DatePrecisionPicker {...defaultProps} />)

    expect(screen.queryByText('Start')).not.toBeInTheDocument()
  })

  it('calls onChange with updated year', () => {
    const onChange = vi.fn()
    render(<DatePrecisionPicker {...defaultProps} onChange={onChange} />)

    fireEvent.change(screen.getByPlaceholderText('Year'), { target: { value: '1990' } })

    expect(onChange).toHaveBeenCalledWith({ year: '1990', month: '', day: '' })
  })

  it('calls onChange with updated month', () => {
    const onChange = vi.fn()
    render(<DatePrecisionPicker {...defaultProps} onChange={onChange} />)

    fireEvent.change(screen.getByPlaceholderText('Month'), { target: { value: '05' } })

    expect(onChange).toHaveBeenCalledWith({ year: '', month: '05', day: '' })
  })

  it('calls onChange with updated day', () => {
    const onChange = vi.fn()
    render(<DatePrecisionPicker {...defaultProps} onChange={onChange} />)

    fireEvent.change(screen.getByPlaceholderText('Day'), { target: { value: '15' } })

    expect(onChange).toHaveBeenCalledWith({ year: '', month: '', day: '15' })
  })

  it('displays current values', () => {
    render(
      <DatePrecisionPicker {...defaultProps} value={{ year: '2020', month: '01', day: '15' }} />,
    )

    expect(screen.getByDisplayValue('2020')).toBeInTheDocument()
    expect(screen.getByDisplayValue('01')).toBeInTheDocument()
    expect(screen.getByDisplayValue('15')).toBeInTheDocument()
  })
})
