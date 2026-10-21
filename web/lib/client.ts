"use client";

// The API runs on a free host that sleeps when nobody uses it and takes about a
// minute to wake up. Network failures and 5xx answers are retried for a while;
// a 4xx answer is final and fails at once. An aborted request stops quietly.
export class ApiError extends Error {}

export async function fetchJSON<T>(url: string, init?: RequestInit, attempts = 8): Promise<T> {
  let last: unknown;
  for (let i = 0; i < attempts; i++) {
    let response: Response | null = null;
    try {
      response = await fetch(url, init);
    } catch (error) {
      if (init?.signal?.aborted) throw error;
      last = error; // network failure: the host may be waking up
    }
    if (response) {
      if (response.ok) return (await response.json()) as T;
      if (response.status < 500) throw new ApiError(`${url}: ${response.status}`);
      last = new ApiError(`${url}: ${response.status}`);
    }
    await new Promise((r) => setTimeout(r, 8000));
    if (init?.signal?.aborted) throw new DOMException("Aborted", "AbortError");
  }
  throw last;
}

export const isAbort = (error: unknown) => error instanceof DOMException && error.name === "AbortError";
