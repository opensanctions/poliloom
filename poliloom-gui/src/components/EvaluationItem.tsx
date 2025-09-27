import { ReactNode } from "react";

interface EvaluationItemProps {
  title: ReactNode;
  children: ReactNode;
  onHover?: () => void;
}

export function EvaluationItem({
  title,
  children,
  onHover,
}: EvaluationItemProps) {
  return (
    <div
      className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors"
      onMouseEnter={onHover}
    >
      <h3 className="font-medium text-gray-900 mb-3">
        {title}
      </h3>
      <div className="space-y-3">{children}</div>
    </div>
  );
}
