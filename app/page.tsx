import Link from "next/link";
import { getStats, getSessions } from "@/lib/api";
import { StatCard } from "@/components/stat-card";
import { BarIndicator } from "@/components/bar-indicator";
import { ConnectionStatus } from "@/components/connection-status";
import { EscalationBadge } from "@/components/escalation-badge";
import { RelativeTime } from "@/components/relative-time";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default async function OverviewPage() {
  let stats;
  let recentSessions;
  let apiError = false;

  try {
    [stats, recentSessions] = await Promise.all([
      getStats(),
      getSessions({ limit: 5 }),
    ]);
  } catch {
    apiError = true;
  }

  if (apiError || !stats || !recentSessions) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
        <p className="text-lg font-medium">Unable to connect to API</p>
        <p className="text-sm mt-1">Make sure the Flask backend is running on port 5000.</p>
      </div>
    );
  }

  const toolMax = Math.max(...Object.values(stats.tool_usage), 1);
  const escMax = Math.max(...Object.values(stats.escalation_distribution), 1);

  const escalationLabels: Record<string, string> = {
    "0": "None",
    "1": "Low",
    "2": "Medium",
    "3": "High",
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Overview</h2>
        <ConnectionStatus />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard title="Total Sessions" value={stats.total_sessions} />
        <StatCard title="Active Sessions" value={stats.active_sessions} />
        <StatCard title="Avg Escalation" value={stats.avg_escalation} />
        <StatCard title="Tokens Deployed" value={stats.total_tokens} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Tool Usage
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {Object.keys(stats.tool_usage).length === 0 ? (
              <p className="text-sm text-muted-foreground">No tool calls recorded yet.</p>
            ) : (
              Object.entries(stats.tool_usage).map(([tool, count]) => (
                <BarIndicator key={tool} label={tool} value={count} max={toolMax} />
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Escalation Distribution
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {Object.keys(stats.escalation_distribution).length === 0 ? (
              <p className="text-sm text-muted-foreground">No sessions yet.</p>
            ) : (
              Object.entries(stats.escalation_distribution).map(([level, count]) => (
                <BarIndicator
                  key={level}
                  label={`${level} - ${escalationLabels[level] ?? level}`}
                  value={count}
                  max={escMax}
                />
              ))
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Recent Sessions
          </CardTitle>
        </CardHeader>
        <CardContent>
          {recentSessions.sessions.length === 0 ? (
            <p className="text-sm text-muted-foreground">No sessions captured yet.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ID</TableHead>
                  <TableHead>Escalation</TableHead>
                  <TableHead>Started</TableHead>
                  <TableHead className="text-right">Interactions</TableHead>
                  <TableHead className="text-right">Tokens</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {recentSessions.sessions.map((s) => (
                  <TableRow key={s.id}>
                    <TableCell>
                      <Link
                        href={`/sessions/${s.id}`}
                        className="font-mono text-sm text-primary hover:underline"
                      >
                        {s.id.slice(0, 12)}...
                      </Link>
                    </TableCell>
                    <TableCell>
                      <EscalationBadge level={s.escalation_level} />
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      <RelativeTime iso={s.started_at} />
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {s.interaction_count}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {s.token_count}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
