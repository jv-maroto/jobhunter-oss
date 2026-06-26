"use client";

import { Copy, ExternalLink, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { useMarkPersonSent } from "@/hooks/usePersons";
import type { Person } from "@/lib/types";

export function ConnectButton({ person }: { person: Person }) {
  const mutation = useMarkPersonSent();

  const handle = async () => {
    try {
      await navigator.clipboard.writeText(person.message);
      toast.success("Mensaje copiado", {
        description: `Pega al conectar con ${person.full_name}`,
        icon: <Copy className="h-4 w-4" />,
      });
    } catch {
      toast.warning("No se pudo copiar al portapapeles");
    }
    window.open(person.profile_url, "_blank", "noopener,noreferrer");
    try {
      await mutation.mutateAsync(person.id);
    } catch {
      /* silencioso */
    }
  };

  return (
    <Button
      size="sm"
      onClick={handle}
      disabled={mutation.isPending}
      shimmer
      className="group"
    >
      {mutation.isPending ? (
        <Loader2 className="animate-spin" />
      ) : (
        <ExternalLink />
      )}
      Copy & Open
    </Button>
  );
}
