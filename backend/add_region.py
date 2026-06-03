"""
Adds a Region/availability column to the dataset.
Sri Lanka regions: Colombo, Kandy, Galle, Jaffna, Negombo, Kurunegala, Anuradhapura
Premium brands tend to be available in major cities.
Run once: python add_region.py
"""
import pandas as pd
import numpy as np
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
CSV_PATH = os.path.join(ROOT_DIR, "dataset", "pc_advisor_laptop_dataset.csv")

df = pd.read_csv(CSV_PATH)

if "Region" in df.columns:
    print("Region column already exists. Skipping.")
else:
    # All regions
    all_regions = ["Colombo", "Kandy", "Galle", "Jaffna", "Negombo", "Kurunegala", "Anuradhapura"]

    # Premium brands available in more regions
    premium_brands = ["Apple", "Microsoft", "MSI", "Razer", "Samsung"]
    common_brands  = ["HP", "Dell", "Lenovo", "ASUS", "Acer", "Gigabyte"]

    def assign_region(row):
        brand = str(row.get("Brand", "")).strip()
        price = float(row.get("Final Price (LKR)", 0) or 0)

        if brand in premium_brands or price > 300_000:
            # Premium — available mainly in Colombo, Kandy, Negombo
            choices = ["Colombo", "Kandy", "Negombo", "Colombo", "Colombo"]
        elif brand in common_brands:
            # Common — available across most regions
            choices = all_regions
        else:
            choices = ["Colombo", "Kandy", "Galle", "Negombo", "Kurunegala"]

        return np.random.choice(choices)

    np.random.seed(42)
    df["Region"] = df.apply(assign_region, axis=1)
    df.to_csv(CSV_PATH, index=False)
    print(f"✅ Region column added to {len(df)} laptops.")
    print(df["Region"].value_counts())
