import RadarView from "@/components/RadarView";

export const metadata = { title: "Order radar · Invoice Block Radar" };

export default function RadarPage() {
  return (
    <>
      <section className="head">
        <p className="eyebrow">The forecaster · at order time</p>
        <h1>Will this order line hit a payment block?</h1>
        <p className="lead">
          A line is scored the moment it is created with the block rate of earlier invoices of the same vendor, for
          the same company and match type, counting only outcomes known that day. It beat two LightGBM models on
          every month it was compared on (see the evidence page).
        </p>
      </section>
      <RadarView />
    </>
  );
}
