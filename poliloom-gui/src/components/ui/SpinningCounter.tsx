'use client'

interface SpinningCounterProps {
  value: number
  className?: string
  minDigits?: number
}

function DigitWheel({ digit }: { digit: number }) {
  return (
    <div className="relative h-5 w-3 overflow-hidden bg-zinc-900 rounded-sm">
      <div
        className="absolute w-full transition-transform duration-500 ease-out"
        style={{
          transform: `translateY(-${digit * 20}px)`,
        }}
      >
        {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9].map((n) => (
          <div
            key={n}
            className="h-5 flex items-center justify-center text-white font-bold text-xs leading-none"
          >
            {n}
          </div>
        ))}
      </div>
      {/* Subtle shine overlay */}
      <div className="absolute inset-0 bg-gradient-to-b from-white/10 via-transparent to-black/20 pointer-events-none" />
    </div>
  )
}

export function SpinningCounter({ value, className = '', minDigits = 4 }: SpinningCounterProps) {
  // Convert to string and pad with zeros, always one extra leading zero
  const valueStr = String(value)
  const padLength = Math.max(minDigits, valueStr.length + 1)
  const digits = valueStr.padStart(padLength, '0').split('').map(Number)

  return (
    <div
      className={`inline-flex items-center gap-[1px] bg-zinc-800 p-[3px] rounded shadow-inner ${className}`}
      style={{ boxShadow: 'inset 0 2px 4px rgba(0,0,0,0.3)' }}
    >
      {digits.map((digit, index) => (
        <DigitWheel key={index} digit={digit} />
      ))}
    </div>
  )
}
