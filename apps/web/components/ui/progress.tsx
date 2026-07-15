export function Progress({ value, label }: { value: number; label: string }) {
  const bounded = Math.max(0, Math.min(100, value));
  return (
    <div
      aria-label={label}
      aria-valuemax={100}
      aria-valuemin={0}
      aria-valuenow={Math.round(bounded)}
      className="h-2 overflow-hidden rounded-full bg-muted"
      role="progressbar"
    >
      <div className="h-full rounded-full bg-primary transition-[width] motion-reduce:transition-none" style={{ width: `${bounded}%` }} />
    </div>
  );
}
