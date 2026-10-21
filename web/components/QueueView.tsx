"use client";

import { Fragment, useEffect, useState } from "react";

import Waking from "@/components/Waking";
import type { CaseDetail, Cause, Queue } from "@/lib/api";
import { fetchJSON, isAbort } from "@/lib/client";
import { CAUSES, RELEASE_REASONS, fmt } from "@/lib/api";

const ORDER: Cause[] = ["likely_mismatch", "routine_check", "waiting_for_goods"];
const PAGE = 25;

// The model sometimes marks words with **bold**; show that as bold, nothing else.
function Rich({ text }: { text: string }) {
  return (
    <>
      {text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
        part.startsWith("**") ? <b key={i}>{part.slice(2, -2)}</b> : <Fragment key={i}>{part}</Fragment>,
      )}
    </>
  );
}

export default function QueueView() {
  const [cause, setCause] = useState<Cause | null>(null);
  const [recorded, setRecorded] = useState(true);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState(""); // the search, once the typing pauses
  const [offset, setOffset] = useState(0);
  const [queue, setQueue] = useState<Queue | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => setQuery(search.trim()), 300);
    return () => clearTimeout(timer);
  }, [search]);

  // Each change cancels the request before it, so an older answer never
  // replaces a newer one.
  useEffect(() => {
    const abort = new AbortController();
    const params = new URLSearchParams({ limit: String(PAGE), offset: String(offset) });
    if (cause) params.set("cause", cause);
    if (recorded) params.set("recorded", "true");
    if (query) params.set("search", query);
    fetchJSON<Queue>(`/api/queue?${params}`, { signal: abort.signal })
      .then((q) => {
        setQueue(q);
        setError(null);
        setSelected((current) =>
          q.items.length && !q.items.some((i) => i.case_id === current) ? q.items[0].case_id : current,
        );
      })
      .catch((e: Error) => !isAbort(e) && setError(e.message));
    return () => abort.abort();
  }, [cause, recorded, query, offset]);

  useEffect(() => {
    if (!selected) return;
    const abort = new AbortController();
    setDetail(null);
    fetchJSON<CaseDetail>(`/api/cases/${selected}`, { signal: abort.signal })
      .then(setDetail)
      .catch((e: Error) => !isAbort(e) && setError(e.message));
    return () => abort.abort();
  }, [selected]);

  const choose = (next: Cause | null) => {
    setCause(next);
    setOffset(0);
  };

  return (
    <div className="queue">
      <div className="cause-cards" role="group" aria-label="Filter by likely cause">
        <button className={`cause-card ${cause === null ? "on" : ""}`} onClick={() => choose(null)}>
          <span className="label">All open blocks</span>
          <span className="value num">
            {queue ? fmt.int(ORDER.reduce((s, c) => s + (queue.by_cause[c]?.blocks ?? 0), 0)) : "…"}
          </span>
          <span className="sub">sorted: likely mismatches first, highest value first</span>
        </button>
        {ORDER.map((c) => (
          <button key={c} className={`cause-card ${CAUSES[c].tone} ${cause === c ? "on" : ""}`} onClick={() => choose(c)}>
            <span className="label">
              <span className={`pill ${CAUSES[c].tone}`}>{CAUSES[c].label}</span>
            </span>
            <span className="value num">{queue ? fmt.int(queue.by_cause[c]?.blocks ?? 0) : "…"}</span>
            <span className="sub">{queue ? `${fmt.eur(queue.by_cause[c]?.value_eur ?? 0)} on hold · ${CAUSES[c].short}` : ""}</span>
          </button>
        ))}
      </div>

      <div className="toolbar">
        <label className="toggle">
          <input
            type="checkbox"
            checked={recorded}
            onChange={(e) => {
              setRecorded(e.target.checked);
              setOffset(0);
            }}
          />
          Only cases written by Mistral ({queue && recorded ? queue.total : 30})
        </label>
        <input
          type="search"
          placeholder="Search a vendor, purchase order or buyer"
          aria-label="Search the queue"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setOffset(0);
          }}
        />
      </div>

      {error && <p className="callout">The API did not answer ({error}). Reload the page in a minute.</p>}
      {!queue && !error && <Waking what="the blocked invoices" />}

      <div className="split">
        <div className="panel list">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Cause</th>
                  <th>Purchase order · vendor</th>
                  <th className="num">Value</th>
                  <th className="num">Days open</th>
                </tr>
              </thead>
              <tbody>
                {queue?.items.map((item) => (
                  <tr
                    key={item.case_id}
                    className={`row ${item.case_id === selected ? "selected" : ""}`}
                    onClick={() => setSelected(item.case_id)}
                    tabIndex={0}
                    onKeyDown={(e) => e.key === "Enter" && setSelected(item.case_id)}
                    aria-selected={item.case_id === selected}
                  >
                    <td>
                      <span className={`pill ${CAUSES[item.cause].tone}`}>{CAUSES[item.cause].short}</span>
                    </td>
                    <td>
                      <span className="mono">{item.po_document}</span>{" "}
                      {item.has_recorded_note && <span className="tag" title="Note written by Mistral">AI note</span>}
                      <div className="note">
                        {item.vendor} · {item.spend_area}
                      </div>
                    </td>
                    <td className="num">{fmt.eur(item.line_value_eur)}</td>
                    <td className="num">{item.days_open}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {queue && (
            <div className="pager">
              <span className="note">
                {fmt.int(offset + 1)}–{fmt.int(Math.min(offset + PAGE, queue.total))} of {fmt.int(queue.total)}
              </span>
              <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
                Previous
              </button>
              <button disabled={offset + PAGE >= queue.total} onClick={() => setOffset(offset + PAGE)}>
                Next
              </button>
            </div>
          )}
        </div>

        <CasePanel detail={detail} />
      </div>
    </div>
  );
}

function CasePanel({ detail }: { detail: CaseDetail | null }) {
  const [copied, setCopied] = useState(false);
  if (!detail) return <aside className="panel case">Loading the case…</aside>;
  const c = detail.case;
  const n = detail.note;
  const email = n.email_subject && n.email_body ? `Subject: ${n.email_subject}\n\n${n.email_body}` : null;
  const copy = async () => {
    if (!email) return;
    try {
      await navigator.clipboard.writeText(email);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  };
  const fixed = ["order_corrected", "invoice_corrected"].includes(detail.outcome.release_reason);

  return (
    <aside className="panel case" aria-live="polite">
      <div className="case-head">
        <span className={`pill ${CAUSES[c.cause].tone}`}>{CAUSES[c.cause].label}</span>
        <h2>
          Purchase order <span className="mono">{c.po_document}</span>
        </h2>
        <p className="note">
          {c.vendor} · {c.company} · {c.spend_area}
        </p>
      </div>

      <dl className="facts">
        <div>
          <dt>Line value</dt>
          <dd className="num">€{fmt.int(c.line_value_eur)}</dd>
        </div>
        <div>
          <dt>Blocked since</dt>
          <dd>
            {new Date(c.blocked_on).toLocaleDateString("en-GB", { day: "numeric", month: "short" })} ·{" "}
            <span className="num">{c.days_open}</span> days
          </dd>
        </div>
        <div>
          <dt>Goods received</dt>
          <dd>{c.goods_received ? "Yes, before the invoice" : "Not yet"}</dd>
        </div>
        <div>
          <dt>Vendor's past blocks</dt>
          <dd>
            <span className="num">{c.vendor_corrections_before}</span> of <span className="num">{c.vendor_blocks_before}</span>{" "}
            needed a fix
          </dd>
        </div>
        <div>
          <dt>Buyer's past blocks</dt>
          <dd>
            <span className="num">{c.buyer_corrections_before}</span> of <span className="num">{c.buyer_blocks_before}</span>{" "}
            needed a fix
          </dd>
        </div>
        <div>
          <dt>Who acts</dt>
          <dd>{c.owner}</dd>
        </div>
      </dl>

      <section className="writeup">
        <h3>Case note</h3>
        <p>
          <Rich text={n.summary} />
        </p>
        <p className="next">
          <b>Next step · </b>
          <Rich text={n.next_step} />
        </p>
      </section>

      {email ? (
        <section className="email">
          <div className="email-head">
            <h3>Draft for the buyer: send if the check confirms a mismatch</h3>
            <button onClick={copy}>{copied ? "Copied" : "Copy"}</button>
          </div>
          <p className="subject">
            <Rich text={n.email_subject!} />
          </p>
          <p className="body">
            <Rich text={n.email_body!} />
          </p>
        </section>
      ) : (
        <p className="note">No email: nothing to ask the vendor for this kind of block.</p>
      )}

      <div className="checks">
        {detail.checks.length === 0 ? (
          <span className="pill ok">Checked in code: no invented figure, email rule respected</span>
        ) : (
          detail.checks.map((p) => (
            <span key={p} className="pill fix">
              {p}
            </span>
          ))
        )}
        <span className="tag">written by {detail.note_source}</span>
      </div>

      <section className={`outcome ${fixed ? "fixed" : ""}`}>
        <h3>What really happened next</h3>
        <p>
          {RELEASE_REASONS[detail.outcome.release_reason]}, released after{" "}
          <span className="num">{detail.outcome.days_blocked}</span> days{" "}
          {detail.outcome.released_by_a_person ? "by a person" : "automatically"}.
        </p>
      </section>
    </aside>
  );
}
