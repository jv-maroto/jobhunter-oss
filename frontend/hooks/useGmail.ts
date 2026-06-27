"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { integrationsApi } from "@/lib/integrations";

export function useGmailStatus() {
  return useQuery({
    queryKey: ["gmail", "status"],
    queryFn: () => integrationsApi.status(),
    staleTime: 30_000,
  });
}

export function useEmailEvents() {
  return useQuery({
    queryKey: ["email-events"],
    queryFn: () => integrationsApi.listEvents(),
    staleTime: 30_000,
  });
}

export function useGmailMutations() {
  const qc = useQueryClient();
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["gmail", "status"] });
    qc.invalidateQueries({ queryKey: ["email-events"] });
    qc.invalidateQueries({ queryKey: ["jobs"] });
    qc.invalidateQueries({ queryKey: ["pipeline"] });
  };
  return {
    connectImap: useMutation({
      mutationFn: (v: { email: string; app_password: string }) =>
        integrationsApi.connectImap(v.email, v.app_password),
      onSuccess: invalidate,
    }),
    disconnect: useMutation({ mutationFn: () => integrationsApi.disconnect(), onSuccess: invalidate }),
    sync: useMutation({ mutationFn: () => integrationsApi.sync(), onSuccess: invalidate }),
    applyEvent: useMutation({ mutationFn: (id: number) => integrationsApi.applyEvent(id), onSuccess: invalidate }),
    dismissEvent: useMutation({ mutationFn: (id: number) => integrationsApi.dismissEvent(id), onSuccess: invalidate }),
    undoEvent: useMutation({ mutationFn: (id: number) => integrationsApi.undoEvent(id), onSuccess: invalidate }),
  };
}
