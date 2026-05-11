import React from 'react';

export interface RxDjangoLogoProps {
  className?: string;
}

export function RxDjangoLogo({ className }: RxDjangoLogoProps) {
  return (
    <svg
      className={className}
      viewBox="0 0 176 36"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="rxdjango"
    >
      <text
        x="0"
        y="28"
        fontFamily="Inter, system-ui, sans-serif"
        fontSize="26"
        fontWeight="600"
        letterSpacing="-0.02em"
      >
        <tspan className="fill-primary-500">
          rx
        </tspan>
        <tspan className="fill-ink">
          django
        </tspan>
      </text>
    </svg>
  );
}

export default RxDjangoLogo;
