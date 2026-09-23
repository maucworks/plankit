export interface VariantSummary {
  id: string;
  parent_id: string | null;
  step: number;
  label: string | null;
  created_at: string;
}

export interface Face {
  id: string;
  label: string;
  points: [number, number][];
}

export interface Door {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface Report {
  conformance: { satisfied: string[]; violated: string[]; missing: string[]; unconstrained: string[] };
  quality: Record<string, unknown>;
}

export interface VariantDetail extends VariantSummary {
  program: unknown;
  report: Report;
  geometry: { faces: Face[]; doors: Door[] };
}

const BASE = "http://localhost:8000";

export async function listVariants(): Promise<VariantSummary[]> {
  const r = await fetch(`${BASE}/variants`);
  return r.json();
}

export async function getVariant(id: string): Promise<VariantDetail> {
  const r = await fetch(`${BASE}/variants/${id}`);
  return r.json();
}

export async function generate(program: unknown, label?: string): Promise<VariantDetail> {
  const r = await fetch(`${BASE}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ program, label }),
  });
  return r.json();
}
