export default function SessionsLoading() {
  return (
    <div className="space-y-6">
      <div className="h-8 w-32 animate-pulse rounded bg-muted" />
      <div className="space-y-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-12 animate-pulse rounded bg-muted" />
        ))}
      </div>
    </div>
  );
}
