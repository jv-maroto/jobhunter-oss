import { cn, scoreTone } from "@/lib/utils";

interface Props {
  score: number;
  reason?: string | null;
  size?: "sm" | "md" | "lg";
  className?: string;
}

export function ScoreBadge({ score, reason, size = "md", className }: Props) {
  const tone = scoreTone(score);
  const heuristic = reason?.includes("Heuristic fit estimate") ?? false;
  return (
    <span
      role="img"
      className="inline-flex shrink-0 flex-col items-center gap-1"
      title={reason || "Fit score 0–100; estimate, not hiring probability."}
      aria-label={`Fit score ${score} out of 100. ${heuristic ? "Heuristic. " : ""}${reason || "Estimate, not hiring probability."}`}
    >
      <span className={cn(
          "inline-flex items-center justify-center rounded-md mono tabular-nums font-semibold",
          tone.bg,
          tone.text,
          tone.ring,
          size === "sm" && "h-5 min-w-[2rem] px-1.5 text-[11px]",
          size === "md" && "h-7 min-w-[2.5rem] px-2 text-xs",
          size === "lg" && "h-10 min-w-[3rem] px-2.5 text-base",
          className,
        )}
      >
        {score}
      </span>
      {heuristic && <span className="text-[9px] leading-tight font-normal text-muted-foreground">Heuristic</span>}
    </span>
  );
}
