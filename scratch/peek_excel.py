import pandas as pd
import os

path = r"c:\Users\USER\Desktop\Projects\DATING APP\questionbank"
files = [f for f in os.listdir(path) if f.endswith('.xlsx')]

for f in files:
    full_path = os.path.join(path, f)
    df = pd.read_excel(full_path, nrows=5)
    print(f"--- {f} ---")
    print("Columns:", df.columns.tolist())
    print("Sample:\n", df.head(2))
    print("\n")
