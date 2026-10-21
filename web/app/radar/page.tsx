import RadarView from "@/components/RadarView";

export const metadata = { title: "Order radar · Invoice Block Radar" };

export default function RadarPage() {
  return (
    <>
      <section className="head">
        <p className="eyebrow">The forecaster · at order time</p>
        <h1>Will this order line hit a payment block?</h1>
        <p className="lead">
          A LightGBM model trained on orders from January to July 2018 scores a line the moment it is created, using
          only what is known then: what is bought, the vendor, the buyer, and how their earlier invoices went. SHAP
          shows which inputs raised or lowered the risk.
        </p>
      </section>
      <RadarView />
    </>
  );
}
