import type { ReactNode } from 'react';

interface SectionProps {
  title: string;
  children: ReactNode;
  className?: string;
}

export default function Section({ title, children, className = '' }: SectionProps) {
  return (
    <div className={`bg-white dark:bg-gray-800 rounded border dark:border-gray-700 p-4 ${className}`}>
      <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">{title}</h3>
      <div className="space-y-3">{children}</div>
    </div>
  );
}
