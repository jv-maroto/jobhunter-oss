import { cn, scoreTone } from "@/lib/utils";

interface Props {
  score: number;
  size?: "sm" | "md" | "lg";
  className?: string;
}

export function ScoreBadge({ score, size = "md", className }: Props) {
  const tone = scoreTone(score);
  return (
    <span
      title={tone.label}
      className={cn(
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
  );
}
