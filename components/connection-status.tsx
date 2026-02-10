"use client";

import { useEventStreamContext } from "@/lib/event-stream-context";

export function ConnectionStatus() {
  const { connected, error } = useEventStreamContext();

  return (
    <div className="flex items-center gap-2 text-xs">
      <span
        className={`inline-block h-2 w-2 rounded-full ${
          connected ? "bg-green-500" : "bg-red-500"
        }`}
        aria-hidden="true"
      />
      <span className="text-muted-foreground">
        {connected ? "Live" : error || "Disconnected"}
      </span>
    </div>
  );
}
