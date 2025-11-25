type DataLabelVariant = 'new' | 'existing'

const variantStyles: Record<DataLabelVariant, string> = {
  new: 'text-blue-600',
  existing: 'text-gray-500',
}

interface DataLabelProps {
  variant: DataLabelVariant
  children: React.ReactNode
}

export function DataLabel({ variant, children }: DataLabelProps) {
  return <span className={`px-2 py-1 text-sm rounded ${variantStyles[variant]}`}>{children}</span>
}
