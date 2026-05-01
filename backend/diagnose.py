# diagnose.py — run from backend/
import os
from dotenv import load_dotenv
load_dotenv()

from data.source import DataSource

ds = DataSource()
print(f"Provider: {ds.provider}")

df = ds.get_bars("SPY", "1Day", limit=500)
print(f"Rows returned: {len(df)}")
print(f"First bar: {df.index[0]}")
print(f"Last bar:  {df.index[-1]}")
print(f"Limit hit: {len(df) == 500}")