'use client'

interface SpinningCounterProps {
  value: number
  className?: string
  minDigits?: number
  title?: string
}

// Height in em units - scales with font size
const DIGIT_HEIGHT_EM = 1.8

function DigitWheel({ digit }: { digit: number }) {
  return (
    <div
      className="relative overflow-hidden bg-gray-50 border-x border-gray-100 first:border-l-0 first:rounded-l last:border-r-0 last:rounded-r"
      style={{ height: `${DIGIT_HEIGHT_EM}em`, width: '1.1em' }}
    >
      <div
        className="absolute w-full transition-transform duration-500 ease-out"
        style={{
          transform: `translateY(-${digit * DIGIT_HEIGHT_EM}em)`,
        }}
      >
        {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9].map((n) => (
          <div
            key={n}
            className="flex items-center justify-center text-gray-700 font-semibold leading-none tabular-nums"
            style={{ height: `${DIGIT_HEIGHT_EM}em` }}
          >
            {n}
          </div>
        ))}
      </div>
    </div>
  )
}

export function SpinningCounter({
  value,
  className = '',
  minDigits = 4,
  title,
}: SpinningCounterProps) {
  // Convert to string and pad with zeros, always one extra leading zero
  const valueStr = String(value)
  const padLength = Math.max(minDigits, valueStr.length + 1)
  const digits = valueStr.padStart(padLength, '0').split('').map(Number)

  return (
    <div
      className={`inline-flex items-center bg-white border border-gray-200 rounded-md overflow-hidden ${className}`}
      title={title}
    >
      {digits.map((digit, index) => (
        <DigitWheel key={index} digit={digit} />
      ))}
    </div>
  )
}
