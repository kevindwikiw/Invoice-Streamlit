import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { InvoicePayload, InvoiceRecord, PackageRecord, DashboardStats } from "../../../shared/contract";
import { apiFetch } from "./client";

export function usePackages() {
  return useQuery({
    queryKey: ["packages"],
    queryFn: () => apiFetch<PackageRecord[]>("/api/packages"),
  });
}

export function useCreatePackage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: Omit<PackageRecord, "id">) =>
      apiFetch<PackageRecord>("/api/packages", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["packages"] }),
  });
}

export function useInvoices() {
  return useQuery({
    queryKey: ["invoices"],
    queryFn: () => apiFetch<InvoiceRecord[]>("/api/invoices"),
  });
}

export function useCreateInvoice() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: InvoicePayload) =>
      apiFetch<InvoiceRecord>("/api/invoices", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["invoices"] }),
  });
}

export function useDashboardStats() {
  return useQuery({
    queryKey: ["dashboard"],
    queryFn: () => apiFetch<DashboardStats>("/api/dashboard"),
  });
}
