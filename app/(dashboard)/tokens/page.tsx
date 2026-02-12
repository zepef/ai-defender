import Link from "next/link";
import { getTokens } from "@/lib/api";
import { MaskedValue } from "@/components/masked-value";
import { TokenTypeBadge } from "@/components/token-type-badge";
import { RelativeTime } from "@/components/relative-time";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export default async function TokensPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | undefined }>;
}) {
  const params = await searchParams;
  const limit = Math.max(1, Math.min(Number(params.limit) || 20, 200));
  const offset = Math.max(0, Number(params.offset) || 0);
  const tokenType = params.token_type;

  let data;
  let apiError = false;

  try {
    data = await getTokens({ token_type: tokenType, limit, offset });
  } catch {
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
      <h2 className="text-2xl font-bold">Honey Tokens</h2>

      {data.tokens.length === 0 ? (
        <p className="text-muted-foreground">No tokens deployed yet.</p>
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Value</TableHead>
                <TableHead>Context</TableHead>
                <TableHead>Session</TableHead>
                <TableHead>Deployed</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.tokens.map((t) => (
                <TableRow key={t.id}>
                  <TableCell className="font-mono text-sm">
                    {t.id}
                  </TableCell>
                  <TableCell>
                    <TokenTypeBadge type={t.token_type} />
                  </TableCell>
                  <TableCell className="max-w-[200px] font-mono text-sm text-muted-foreground">
                    <MaskedValue value={t.token_value} />
                  </TableCell>
                  <TableCell className="max-w-[200px] truncate text-sm text-muted-foreground">
                    {t.context}
                  </TableCell>
                  <TableCell>
                    {t.session_id && (
                      <Link
                        href={`/sessions/${t.session_id}`}
                        className="font-mono text-sm text-primary hover:underline"
                      >
                        {t.session_id.slice(0, 12)}...
                      </Link>
                    )}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    <RelativeTime iso={t.deployed_at} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              Showing {data.total > 0 ? offset + 1 : 0}-{Math.min(offset + limit, data.total)} of{" "}
              {data.total}
            </p>
            <div className="flex gap-2">
              {hasPrev && (
                <Link
                  href={`/tokens?limit=${limit}&offset=${Math.max(0, offset - limit)}${tokenType ? `&token_type=${tokenType}` : ""}`}
                  className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-accent"
                >
                  Previous
                </Link>
              )}
              {hasNext && (
                <Link
                  href={`/tokens?limit=${limit}&offset=${offset + limit}${tokenType ? `&token_type=${tokenType}` : ""}`}
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
