type DataLabelVariant = 'new' | 'existing'

const variantConfig: Record<DataLabelVariant, { text: string; className: string }> = {
  new: { text: 'New data 🎉', className: 'text-accent-foreground' },
  existing: { text: 'Existing data', className: 'text-foreground-muted' },
}

interface DataLabelProps {
  variant: DataLabelVariant
}

export function DataLabel({ variant }: DataLabelProps) {
  const { text, className } = variantConfig[variant]
  return <span className={`py-1 text-sm rounded ${className}`}>{text}</span>
}
