# Data

The project uses the **BPI Challenge 2019** event log: purchase-to-pay data from a
large multinational company in coatings and paints (about 60 subsidiaries), covering
purchase orders created in 2018.

- Download: [Kaggle mirror](https://www.kaggle.com/datasets/aaminaalzeri/bpi-challenge-2019-dataset)
  (`BPI_Challenge_2019.xes`, 728.6 MB unzipped)
- Original publication: van Dongen, B.F. (2019), *BPI Challenge 2019*, 4TU.ResearchData,
  DOI [10.4121/uuid:d06aff4b-79f0-45e6-8ec8-e19730c248f1](https://doi.org/10.4121/uuid:d06aff4b-79f0-45e6-8ec8-e19730c248f1)
- Terms of use: those of the original publication; the Kaggle mirror lists CC BY-SA 4.0

The file is not committed. Put it in `data/raw/`, then run:

```bash
python scripts/ingest.py data/raw/BPI_Challenge_2019.xes data/parquet
```

Expected output: `251,734 items, 1,595,923 events`.

SHA-256 of the file used here:
`af63bc687fc4152f2123b05c3af7772b37ef3fce2d3f67f812666c9e356baae7`
