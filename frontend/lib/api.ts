import type { Scenario } from "./types";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export const WS_BASE_URL =
  process.env.NEXT_PUBLIC_WS_BASE_URL ?? "ws://localhost:8000";

export async function fetchScenarios(): Promise<Scenario[]> {
  const res = await fetch(`${API_BASE_URL}/scenarios`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Failed to load scenarios: ${res.status}`);
  }
  return res.json();
}

export async function fetchScenario(scenarioId: string): Promise<Scenario> {
  const res = await fetch(`${API_BASE_URL}/scenarios/${scenarioId}`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Failed to load scenario '${scenarioId}': ${res.status}`);
  }
  return res.json();
}
