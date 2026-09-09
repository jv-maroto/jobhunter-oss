import type { QualificationAssessment } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const RECOMMENDATIONS: Record<QualificationAssessment["recommendation"], string> = {
  strong: "Evidence matches the detected requirements",
  consider: "Worth considering",
  stretch: "Some requirements need more evidence",
  unlikely: "A required qualification is not met",
  unknown: "Requirements need review",
};

export function QualificationChecks({ assessment }: { assessment?: QualificationAssessment | null }) {
  const required = assessment?.checks.filter((check) => check.importance === "required") ?? [];
  const other = assessment?.checks.filter((check) => check.importance !== "required") ?? [];
  const row = (check: QualificationAssessment["checks"][number], index: number) => <li key={`${check.kind}-${index}`} className="py-4 first:pt-0 last:pb-0 space-y-2">
    <div className="flex flex-wrap gap-2 items-center">
      <Badge variant={check.status === "gap" ? "destructive" : check.status === "met" ? "default" : "secondary"}>{check.status === "met" ? "Evidence found" : check.status === "gap" ? "Gap" : "Unconfirmed"}</Badge>
      <span className="text-xs text-muted-foreground capitalize">{check.kind} · {check.importance}</span>
    </div>
    <p className="text-sm break-words">{check.requirement}</p>
    <p className="text-sm text-muted-foreground break-words">{check.evidence || "Your saved profile does not establish this requirement."}</p>
  </li>;
  return <Card variant="glass">
    <CardHeader>
      <CardTitle>Requirements check</CardTitle>
      <p className="text-sm text-muted-foreground">{assessment?.summary || "Review the full posting against your profile. A fit score alone does not establish eligibility."}</p>
      {assessment && <p className="text-sm font-medium">{RECOMMENDATIONS[assessment.recommendation]}</p>}
    </CardHeader>
    <CardContent className="space-y-4">
      {required.length ? <ul className="divide-y divide-border">{required.map(row)}</ul> : <p className="text-sm text-muted-foreground">No explicit mandatory requirements were identified. Check the original description before deciding.</p>}
      {other.length > 0 && <details className="rounded-lg border border-border p-4">
        <summary className="cursor-pointer text-sm font-medium">Other detected qualifications ({other.length})</summary>
        <p className="mt-3 text-xs text-muted-foreground">Preferences and ambiguous wording need your review. These do not establish mandatory eligibility.</p>
        <ul className="mt-4 divide-y divide-border">{other.map(row)}</ul>
      </details>}
    </CardContent>
  </Card>;
}
