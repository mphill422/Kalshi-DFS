name: PropLine Edge Test

on:
  schedule:
    # Runs at 5 PM and 9 PM UTC (1 PM / 5 PM ET) — before MLB games lock,
    # when PrizePicks/Underdog lines are posted. Adjust if you like.
    - cron: "0 17 * * *"
    - cron: "0 21 * * *"
  workflow_dispatch: {}   # lets you run it manually from the Actions tab

jobs:
  edge-test:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install deps
        run: pip install numpy pandas requests

      - name: Run PropLine edge test
        env:
          PROPLINE_API_KEY: ${{ secrets.PROPLINE_API_KEY }}
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
        run: python propline_edge_test.py
