import QueueView from "@/components/QueueView";
import type { Queue } from "@/lib/api";
import { fmt, getJSON } from "@/lib/api";

export const metadata = { title: "Blocked queue · Invoice Block Radar" };

export default async function QueuePage() {
  const queue = await getJSON<Queue>("/api/queue?limit=1");
  return (
    <>
      <section className="head">
        <p className="eyebrow">The detective · 15 October 2018</p>
        <h1>{fmt.int(queue.total)} invoices were on hold that morning. Here is the pile, sorted.</h1>
        <p className="lead">
          Rules decide the likely cause, who should act and whether the vendor needs an email; the language model only
          writes, and every note is checked in code. Each case also shows what really happened next, from the log.
        </p>
      </section>
      <QueueView />
    </>
  );
}
