interface DateRangeProps {
  startDate: string | null;
  endDate: string | null;
}

export function DateRange({ startDate, endDate }: DateRangeProps) {
  // Show "No dates set" when both dates are null
  if (!startDate && !endDate) {
    return (
      <p className="text-gray-500 italic mt-1">
        No dates set
      </p>
    );
  }

  const displayStart = startDate || 'Unknown';
  const displayEnd = endDate || 'Present';

  return (
    <p className="text-gray-700 mt-1">
      {displayStart} - {displayEnd}
    </p>
  );
}