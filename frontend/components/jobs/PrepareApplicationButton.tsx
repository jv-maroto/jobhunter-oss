"use client";

import { Loader2, Wand2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { usePrepareApplication } from "@/hooks/useJobs";
import type { Job } from "@/lib/types";
import { useLang } from "@/lib/i18n";

export function PrepareApplicationButton({
  job,
  variant = "default",
  size = "sm",
}: {
  job: Job;
  variant?: "default" | "solid" | "outline" | "glass";
  size?: "sm" | "default";
}) {
  const { t } = useLang();
  const mutation = usePrepareApplication();
  const router = useRouter();

  const generateAndOpen = async () => {
    try {
      const prepared = await mutation.mutateAsync(job.id);
      router.push(`/applications/${prepared.application_id}`);
      toast.success(t("application_documents_ready"), {
        description:
          "Review your CV and cover letter before opening the employer's application form.",
        duration: 15000,
      });
    } catch (e) {
      toast.error(t("prepare_application_failed"), { description: String(e) });
    }
  };

  return (
    <Button
      size={size}
      variant={variant}
      onClick={generateAndOpen}
      disabled={mutation.isPending}
      shimmer={variant === "default" || variant === "solid"}
      className="group"
    >
      {mutation.isPending ? (
        <Loader2 className="animate-spin" />
      ) : (
        <Wand2 />
      )}
      {mutation.isPending ? t("preparing_application") : t("prepare_application")}
    </Button>
  );
}
