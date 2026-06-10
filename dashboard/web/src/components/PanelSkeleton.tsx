export function PanelSkeleton({ lines = 4 }: { lines?: number }) {
  return (
    <div className="space-y-2 animate-pulse" aria-hidden>
      {Array.from({ length: lines }, (_, i) => (
        <div
          key={i}
          className="h-3 rounded bg-liaison-surface-container"
          style={{ width: `${70 - i * 8}%` }}
        />
      ))}
    </div>
  );
}
