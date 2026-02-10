"use client";

import { useState } from "react";

export function MaskedValue({
  value,
  className,
}: {
  value: string;
  className?: string;
}) {
  const [revealed, setRevealed] = useState(false);

  return (
    <span className={className}>
      {revealed ? value : "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022"}
      <button
        type="button"
        onClick={() => setRevealed((r) => !r)}
        className="ml-2 text-xs text-primary hover:underline"
        aria-label={revealed ? "Hide value" : "Reveal value"}
      >
        {revealed ? "hide" : "show"}
      </button>
    </span>
  );
}
