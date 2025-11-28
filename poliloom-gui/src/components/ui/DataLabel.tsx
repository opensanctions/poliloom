type DataLabelVariant = 'new' | 'existing'

const variantConfig: Record<DataLabelVariant, { text: string; className: string }> = {
  new: { text: 'New data 🎉', className: 'text-blue-600' },
  existing: { text: 'Existing data', className: 'text-gray-500' },
}

interface DataLabelProps {
  variant: DataLabelVariant
}

export function DataLabel({ variant }: DataLabelProps) {
  const { text, className } = variantConfig[variant]
  return <span className={`py-1 text-sm rounded ${className}`}>{text}</span>
}
