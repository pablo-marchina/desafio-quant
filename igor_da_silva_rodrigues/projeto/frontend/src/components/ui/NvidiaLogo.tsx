import React from 'react'

export const NvidiaLogo: React.FC<{ size?: number; className?: string }> = ({
  size = 32,
  className = '',
}) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 32 32"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={className}
    aria-label="NVIDIA logo"
  >
    {/* Simplified NVIDIA eye/arc logo mark */}
    <rect width="32" height="32" rx="6" fill="var(--accent)" />
    <path
      d="M6 21V11h2.5l5.5 7V11H16v10h-2.4L8 14v7H6zM18 11h4c2.8 0 4.5 1.8 4.5 5s-1.7 5-4.5 5h-4V11zm2.2 8.2h1.6c1.6 0 2.5-1 2.5-3.2s-.9-3.2-2.5-3.2h-1.6v6.4z"
      fill="var(--text-inverse)"
    />
  </svg>
)
