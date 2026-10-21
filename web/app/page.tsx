import { MonthlyRate, ReleaseReasons } from "@/components/OverviewCharts";
import ProcessFlow from "@/components/ProcessFlow";
import { fmt } from "@/lib/api";
import { evaluation as loadEvaluation, overview as loadOverview, processMap } from "@/lib/data";

export default async function OverviewPage() {
  const [overview, map, evaluation] = await Promise.all([loadOverview(), processMap(), loadEvaluation()]);
  const released = overview.release_reasons.find((r) => r.release_reason === "released_after_review")!;
  const totalBlocks = overview.release_reasons.reduce((s, r) => s + r.blocks, 0);
  const forecast = evaluation.forecast.test_scores["LightGBM model"];

  return (
    <>
      <section className="head">
        <p className="eyebrow">The problem</p>
        <h1>One purchase order line in five hits a payment block before it is paid.</h1>
        <p className="lead">
          The company pays only when the order, the goods receipt and the invoice agree. When they do not, the ERP
          blocks the payment and someone has to investigate. This is what happened to every order line created in
          2018 at a multinational in coatings and paints.
        </p>
      </section>

      <section className="kpis" aria-label="Key figures">
        <div className="kpi hold">
          <span className="value">{fmt.pct(overview.blocked_share, 1)}</span>
          <span className="label">
            of {fmt.int(overview.items)} order lines had their payment blocked ({fmt.int(overview.blocked_items)})
          </span>
        </div>
        <div className="kpi hold">
          <span className="value">{fmt.pct(overview.blocked_value_share, 1)}</span>
          <span className="label">of the order value went through a block</span>
        </div>
        <div className="kpi fix">
          <span className="value">{fmt.pct(overview.releases.by_a_person / overview.releases.releases)}</span>
          <span className="label">
            of releases were done by hand, by just {overview.releases.people} people
          </span>
        </div>
        <div className="kpi">
          <span className="value">{fmt.pct(released.blocks / totalBlocks)}</span>
          <span className="label">of blocks ended with nothing corrected: a check, then a release</span>
        </div>
      </section>

      <section className="panel">
        <div>
          <h2>How a blocked invoice really travels</h2>
          <p className="sub">
            Process mining on the {fmt.int(overview.blocked_items)} blocked items: the ten busiest steps and the
            transitions between them. Moving dots are invoices; hover a line for its count and median delay.
          </p>
        </div>
        <ProcessFlow map={map} />
        <p className="note">
          The theory is order, goods, invoice, payment. The log shows {fmt.int(overview.variants.distinct_paths)}{" "}
          distinct paths for this kind of order; the ten most common cover only{" "}
          {fmt.pct(overview.variants.top_10_paths_share)} of items.
        </p>
      </section>

      <section className="grid-2">
        <div className="panel">
          <div>
            <h2>How the blocks ended</h2>
            <p className="sub">Read from what happened between the invoice and the release. The log never says why.</p>
          </div>
          <ReleaseReasons overview={overview} />
        </div>
        <div className="panel">
          <div>
            <h2>Block rate by month the order was created</h2>
            <p className="sub">Invoiced 3-way-match lines. The last months fall because many invoices were still open.</p>
          </div>
          <MonthlyRate overview={overview} />
        </div>
      </section>

      <section className="panel callout" style={{ background: "var(--accent-soft)" }}>
        <h2>What the radar does about it</h2>
        <p>
          <b>Before:</b> when an order line is created, a model trained on January to July 2018 scores its risk. On
          September and October orders it never saw, checking the riskiest 20% catches{" "}
          <b>{fmt.pct(forecast.share_of_blocks_caught)}</b> of future blocks, twice what a random check finds.{" "}
          <b>After:</b> when an invoice blocks anyway, the detective reads the case, says what is likely wrong and who
          should act, and drafts the vendor email. Open the <a href="/queue">blocked queue</a> or try the{" "}
          <a href="/radar">order radar</a>.
        </p>
      </section>
    </>
  );
}
