interface DateRangeProps {
  startDate: string | null;
  endDate: string | null;
}

export function DateRange({ startDate, endDate }: DateRangeProps) {
  // Only render if we have at least one date
  if (!startDate && !endDate) {
    return null;
  }

  const displayStart = startDate || 'Unknown';
  const displayEnd = endDate || 'Present';

  return (
    <p className="text-gray-700 mt-1">
      {displayStart} - {displayEnd}
    </p>
  );
}