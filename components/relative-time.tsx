"use client";

import { useEffect, useMemo, useState } from "react";

function formatRelative(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function RelativeTime({ iso }: { iso: string }) {
  const initial = useMemo(() => formatRelative(iso), [iso]);
  const [text, setText] = useState(initial);

  useEffect(() => {
    const interval = setInterval(() => setText(formatRelative(iso)), 60_000);
    return () => clearInterval(interval);
  }, [iso]);

  return (
    <time dateTime={iso} title={new Date(iso).toLocaleString()} suppressHydrationWarning>
      {text}
    </time>
  );
}
