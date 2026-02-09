import Link from "next/link";
import { notFound } from "next/navigation";
import { getSession, getSessionInteractions, getSessionTokens } from "@/lib/api";
import { StatCard } from "@/components/stat-card";
import { EscalationBadge } from "@/components/escalation-badge";
import { TokenTypeBadge } from "@/components/token-type-badge";
import { RelativeTime } from "@/components/relative-time";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

function truncate(s: string, max: number): string {
  return s.length > max ? s.slice(0, max) + "..." : s;
}

function duration(start: string, end: string): string {
  const ms = new Date(end).getTime() - new Date(start).getTime();
  const secs = Math.floor(ms / 1000);
  if (secs < 60) return `${secs}s`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ${secs % 60}s`;
  const hours = Math.floor(mins / 60);
  return `${hours}h ${mins % 60}m`;
}

export default async function SessionDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let session;
  let interactionsData;
  let tokensData;

  try {
    [session, interactionsData, tokensData] = await Promise.all([
      getSession(id),
      getSessionInteractions(id),
      getSessionTokens(id),
    ]);
  } catch {
    notFound();
  }

  if (!session) notFound();

  const interactions = interactionsData.interactions;
  const tokens = tokensData.tokens;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link
          href="/sessions"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          Sessions
        </Link>
        <span className="text-muted-foreground">/</span>
        <h2 className="font-mono text-lg font-bold">{id.slice(0, 16)}...</h2>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Escalation
            </CardTitle>
          </CardHeader>
          <CardContent>
            <EscalationBadge level={session.escalation_level} />
          </CardContent>
        </Card>
        <StatCard title="Interactions" value={session.interaction_count} />
        <StatCard title="Tokens Deployed" value={session.token_count} />
        <StatCard
          title="Duration"
          value={duration(session.started_at, session.last_seen_at)}
        />
      </div>

      <Tabs defaultValue="timeline">
        <TabsList>
          <TabsTrigger value="timeline">Timeline</TabsTrigger>
          <TabsTrigger value="tokens">Honey Tokens</TabsTrigger>
          <TabsTrigger value="discovery">Discovery</TabsTrigger>
        </TabsList>

        <TabsContent value="timeline" className="mt-4">
          {interactions.length === 0 ? (
            <p className="text-muted-foreground">No interactions recorded.</p>
          ) : (
            <ScrollArea className="h-[500px] rounded-md border border-border">
              <div className="divide-y divide-border">
                {interactions.map((i) => (
                  <div key={i.id} className="flex gap-4 p-4">
                    <div className="flex flex-col items-center gap-1">
                      <div className="h-2 w-2 rounded-full bg-primary" />
                      <div className="flex-1 w-px bg-border" />
                    </div>
                    <div className="flex-1 space-y-1">
                      <div className="flex items-center gap-2">
                        {i.tool_name && (
                          <Badge variant="outline" className="font-mono text-xs">
                            {i.tool_name}
                          </Badge>
                        )}
                        <span className="text-xs text-muted-foreground">
                          {i.method}
                        </span>
                        {i.escalation_delta > 0 && (
                          <Badge className="bg-red-900/50 text-red-400 text-xs hover:bg-red-900/50">
                            +{i.escalation_delta}
                          </Badge>
                        )}
                        <span className="ml-auto text-xs text-muted-foreground">
                          <RelativeTime iso={i.timestamp} />
                        </span>
                      </div>
                      <pre className="text-xs text-muted-foreground whitespace-pre-wrap break-all">
                        {truncate(JSON.stringify(i.params, null, 2), 300)}
                      </pre>
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>
          )}
        </TabsContent>

        <TabsContent value="tokens" className="mt-4">
          {tokens.length === 0 ? (
            <p className="text-muted-foreground">No tokens deployed in this session.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead>Value</TableHead>
                  <TableHead>Context</TableHead>
                  <TableHead>Deployed</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tokens.map((t) => (
                  <TableRow key={t.id}>
                    <TableCell>
                      <TokenTypeBadge type={t.token_type} />
                    </TableCell>
                    <TableCell
                      className="max-w-[250px] truncate font-mono text-sm text-muted-foreground"
                      title={t.token_value}
                    >
                      {t.token_value}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {t.context}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      <RelativeTime iso={t.deployed_at} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </TabsContent>

        <TabsContent value="discovery" className="mt-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Discovered Hosts
                </CardTitle>
              </CardHeader>
              <CardContent>
                {session.discovered_hosts.length === 0 ? (
                  <p className="text-sm text-muted-foreground">None</p>
                ) : (
                  <ul className="space-y-1">
                    {session.discovered_hosts.map((h: string, i: number) => (
                      <li key={i} className="font-mono text-sm">{h}</li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Discovered Ports
                </CardTitle>
              </CardHeader>
              <CardContent>
                {session.discovered_ports.length === 0 ? (
                  <p className="text-sm text-muted-foreground">None</p>
                ) : (
                  <ul className="space-y-1">
                    {session.discovered_ports.map((p: string, i: number) => (
                      <li key={i} className="font-mono text-sm">{p}</li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Discovered Files
                </CardTitle>
              </CardHeader>
              <CardContent>
                {session.discovered_files.length === 0 ? (
                  <p className="text-sm text-muted-foreground">None</p>
                ) : (
                  <ul className="space-y-1">
                    {session.discovered_files.map((f: string, i: number) => (
                      <li key={i} className="font-mono text-sm">{f}</li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Discovered Credentials
                </CardTitle>
              </CardHeader>
              <CardContent>
                {session.discovered_credentials.length === 0 ? (
                  <p className="text-sm text-muted-foreground">None</p>
                ) : (
                  <ul className="space-y-1">
                    {session.discovered_credentials.map((c: string, i: number) => (
                      <li key={i} className="font-mono text-sm">{c}</li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
