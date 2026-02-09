import Link from "next/link";
import { getSessions } from "@/lib/api";
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

export default async function SessionsPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | undefined }>;
}) {
  const params = await searchParams;
  const limit = Math.max(1, Math.min(Number(params.limit) || 20, 200));
  const offset = Math.max(0, Number(params.offset) || 0);

  let data;
  let apiError = false;

  try {
    data = await getSessions({ limit, offset });
  } catch (err) {
    console.error("Failed to fetch sessions:", err);
    apiError = true;
  }

  if (apiError || !data) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
        <p className="text-lg font-medium">Unable to connect to API</p>
        <p className="text-sm mt-1">Make sure the Flask backend is running on port 5000.</p>
      </div>
    );
  }

  const hasPrev = offset > 0;
  const hasNext = offset + limit < data.total;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Sessions</h2>

      {data.sessions.length === 0 ? (
        <p className="text-muted-foreground">No sessions captured yet.</p>
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Client</TableHead>
                <TableHead>Escalation</TableHead>
                <TableHead>Started</TableHead>
                <TableHead>Last Seen</TableHead>
                <TableHead className="text-right">Interactions</TableHead>
                <TableHead className="text-right">Tokens</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.sessions.map((s) => (
                <TableRow key={s.id}>
                  <TableCell>
                    <Link
                      href={`/sessions/${s.id}`}
                      className="font-mono text-sm text-primary hover:underline"
                    >
                      {s.id.slice(0, 12)}...
                    </Link>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {s.client_info?.name || "unknown"}
                  </TableCell>
                  <TableCell>
                    <EscalationBadge level={s.escalation_level} />
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    <RelativeTime iso={s.started_at} />
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    <RelativeTime iso={s.last_seen_at} />
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

          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              Showing {offset + 1}-{Math.min(offset + limit, data.total)} of{" "}
              {data.total}
            </p>
            <div className="flex gap-2">
              {hasPrev && (
                <Link
                  href={`/sessions?limit=${limit}&offset=${Math.max(0, offset - limit)}`}
                  className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-accent"
                >
                  Previous
                </Link>
              )}
              {hasNext && (
                <Link
                  href={`/sessions?limit=${limit}&offset=${offset + limit}`}
                  className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-accent"
                >
                  Next
                </Link>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
