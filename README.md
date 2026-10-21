# Invoice Block Radar

Predicts which purchase order lines will hit an invoice payment block, and prepares
the fix for the ones that still do.

> Work in progress. This README grows with each step of the project.

## The problem

A large company pays a supplier only when three documents agree: the purchase order,
the goods receipt and the invoice. When they do not, the ERP blocks the payment and
someone has to investigate, chase colleagues and the supplier, correct and release it.

In the public **BPI Challenge 2019** log (purchase-to-pay data from a multinational in
coatings and paints), **55,839 of 251,734 purchase order items (22%)** had a payment
block removed before payment.

## Data

See [data/README.md](data/README.md) to download the log and rebuild the tables.

```bash
pip install -r requirements.txt
python scripts/ingest.py data/raw/BPI_Challenge_2019.xes data/parquet
cd warehouse && dbt build --profiles-dir .
```

## Licence

Code under the MIT licence. The event log keeps the terms of its original publication.
