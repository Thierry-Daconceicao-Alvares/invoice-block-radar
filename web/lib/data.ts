// Server-side data for the pages that never change between visits (overview,
// evidence). They are read from the repository's own files at build time, so
// those pages are static and load instantly even while the API is asleep.
// When the files are not there (the web folder deployed on its own), the
// same data comes from the API.

import { readFile } from "node:fs/promises";
import path from "node:path";

import type { Evaluation, Overview, ProcessMap } from "@/lib/api";
import { getJSON } from "@/lib/api";

const ROOT = path.join(process.cwd(), "..");

async function local<T>(...parts: string[]): Promise<T | null> {
  try {
    return JSON.parse(await readFile(path.join(ROOT, ...parts), "utf8")) as T;
  } catch {
    return null;
  }
}

export async function overview(): Promise<Overview> {
  return (await local<Overview>("data", "demo", "overview.json")) ?? getJSON<Overview>("/api/overview");
}

export async function processMap(): Promise<ProcessMap> {
  return (await local<ProcessMap>("data", "demo", "process_map.json")) ?? getJSON<ProcessMap>("/api/process-map");
}

export async function evaluation(): Promise<Evaluation> {
  const names = ["forecast", "forecast_curves", "triage", "triage_curves", "detective", "writer"] as const;
  const files = await Promise.all(names.map((n) => local<unknown>("docs", "results", `${n}.json`)));
  if (files.every(Boolean)) return Object.fromEntries(names.map((n, i) => [n, files[i]])) as Evaluation;
  return getJSON<Evaluation>("/api/evaluation");
}
