import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const tokenColors: Record<string, string> = {
  aws: "bg-amber-900/50 text-amber-400 hover:bg-amber-900/50",
  api: "bg-blue-900/50 text-blue-400 hover:bg-blue-900/50",
  db: "bg-purple-900/50 text-purple-400 hover:bg-purple-900/50",
  admin: "bg-red-900/50 text-red-400 hover:bg-red-900/50",
  ssh: "bg-green-900/50 text-green-400 hover:bg-green-900/50",
};

export function TokenTypeBadge({ type }: { type: string }) {
  const colorClass = tokenColors[type] ?? "bg-zinc-800 text-zinc-400 hover:bg-zinc-800";
  return (
    <Badge variant="secondary" className={cn("font-mono text-xs uppercase", colorClass)}>
      {type}
    </Badge>
  );
}
