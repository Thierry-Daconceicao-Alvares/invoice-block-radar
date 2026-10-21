"use client";

// The API runs on a free host that sleeps when nobody uses it and takes about a
// minute to wake up. Requests are retried for a while instead of failing at once.
export async function fetchJSON<T>(url: string, init?: RequestInit, attempts = 8): Promise<T> {
  let last: unknown;
  for (let i = 0; i < attempts; i++) {
    try {
      const response = await fetch(url, init);
      if (response.ok) return (await response.json()) as T;
      if (response.status < 500) throw new Error(`${url}: ${response.status}`);
      last = new Error(`${url}: ${response.status}`);
    } catch (error) {
      last = error;
    }
    await new Promise((r) => setTimeout(r, 8000));
  }
  throw last;
}
