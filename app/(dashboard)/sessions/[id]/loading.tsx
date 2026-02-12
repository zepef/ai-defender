export default function SessionDetailLoading() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="h-5 w-16 animate-pulse rounded bg-muted" />
        <div className="h-5 w-1 bg-muted" />
        <div className="h-6 w-40 animate-pulse rounded bg-muted" />
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-24 animate-pulse rounded-lg border border-border bg-muted" />
        ))}
      </div>
      <div className="h-[500px] animate-pulse rounded-lg border border-border bg-muted" />
    </div>
  );
}
