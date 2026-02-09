import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const levels: Record<number, { label: string; className: string }> = {
  0: { label: "None", className: "bg-green-900/50 text-green-400 hover:bg-green-900/50" },
  1: { label: "Low", className: "bg-yellow-900/50 text-yellow-400 hover:bg-yellow-900/50" },
  2: { label: "Medium", className: "bg-orange-900/50 text-orange-400 hover:bg-orange-900/50" },
  3: { label: "High", className: "bg-red-900/50 text-red-400 hover:bg-red-900/50" },
};

export function EscalationBadge({ level }: { level: number }) {
  const config = levels[level] ?? levels[0];
  return (
    <Badge variant="secondary" className={cn("font-mono text-xs", config.className)}>
      {level} - {config.label}
    </Badge>
  );
}
