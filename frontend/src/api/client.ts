import type { ApiResponse } from "../../../shared/contract";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:3001";

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "API request failed");
  }

  const json = (await response.json()) as ApiResponse<T>;
  return json.data;
}
