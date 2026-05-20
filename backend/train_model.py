import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_absolute_error, r2_score
import pickle

# ── Load dataset ──────────────────────────────────────────────────────────────
df = pd.read_csv("../dataset/pc_advisor_laptop_dataset.csv")
print(f"✅ Loaded {len(df)} laptops")
print(f"Columns: {list(df.columns)}")

# ── Clean columns ─────────────────────────────────────────────────────────────
# Remove "GB" from RAM and Storage
df["RAM"] = df["RAM"].astype(str).str.replace("GB", "").str.strip()
df["RAM"] = pd.to_numeric(df["RAM"], errors="coerce")

df["Storage"] = df["Storage"].astype(str).str.replace("GB", "").str.replace("TB", "000").str.strip()
df["Storage"] = pd.to_numeric(df["Storage"], errors="coerce")

# Extract screen size number from string like '14.0" FHD'
df["Screen"] = df["Screen"].astype(str).str.extract(r'(\d+\.?\d*)').astype(float)

# Price is already in LKR
df["Price_LKR"] = pd.to_numeric(df["Final Price (LKR)"], errors="coerce")

df = df.dropna(subset=["Price_LKR", "RAM", "Storage"])
print(f"✅ After cleaning: {len(df)} laptops")

# ── Feature engineering ───────────────────────────────────────────────────────
df["value_score"] = (
    (df["RAM"] / df["Price_LKR"]) * 100000 +
    (df["Storage"] / df["Price_LKR"]) * 10000
)

df["has_discrete_gpu"] = df["GPU"].apply(
    lambda x: 0 if pd.isna(x) or str(x).strip() == "" or
    any(k in str(x).lower() for k in ["intel", "integrated", "uhd", "iris"])
    else 1
)

le_brand = LabelEncoder()
df["brand_encoded"] = le_brand.fit_transform(df["Brand"].fillna("Unknown"))

def cpu_tier(cpu):
    cpu = str(cpu).lower()
    if "i9" in cpu or "ryzen 9" in cpu or "ultra 9" in cpu:
        return 3
    elif "i7" in cpu or "ryzen 7" in cpu or "ultra 7" in cpu:
        return 2
    elif "i5" in cpu or "ryzen 5" in cpu or "ultra 5" in cpu:
        return 1
    else:
        return 0

df["cpu_tier"] = df["CPU"].apply(cpu_tier)

# ── Features and target ───────────────────────────────────────────────────────
features = ["RAM", "Storage", "Price_LKR", "has_discrete_gpu", "brand_encoded", "cpu_tier"]
X = df[features]
y = df["value_score"]

# ── Train/test split ──────────────────────────────────────────────────────────
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# ── Train Random Forest model ─────────────────────────────────────────────────
model = RandomForestRegressor(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# ── Evaluate ──────────────────────────────────────────────────────────────────
y_pred = model.predict(X_test)
mae = mean_absolute_error(y_test, y_pred)
r2 = r2_score(y_test, y_pred)

print(f"\n✅ Model trained successfully!")
print(f"📊 Mean Absolute Error: {mae:.4f}")
print(f"📊 R² Score: {r2:.4f}")
print(f"📊 Feature importances:")
for feat, imp in zip(features, model.feature_importances_):
    print(f"   {feat}: {imp:.4f}")

# ── Save model and encoder ────────────────────────────────────────────────────
with open("../model/recommendation_model.pkl", "wb") as f:
    pickle.dump(model, f)

with open("../brand_encoder.pkl", "wb") as f:
    pickle.dump(le_brand, f)

print("\n✅ Model saved as recommendation_model.pkl")
print("✅ Brand encoder saved as brand_encoder.pkl")