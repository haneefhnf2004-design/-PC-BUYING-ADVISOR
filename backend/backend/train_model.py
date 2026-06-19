"""
PCAdvisor — Model Training Script
Trains three models as specified in the project proposal:
  1. Random Forest  → value scoring / ranking
  2. KNN            → recommendation (find similar laptops)
  3. Ridge Regression → price prediction
Run from the backend/ directory: python train_model.py
"""
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.neighbors import KNeighborsRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import mean_absolute_error, r2_score
import pickle
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)

# ── Load dataset ──────────────────────────────────────────────────────────────
df = pd.read_csv(os.path.join(ROOT_DIR, "dataset", "pc_advisor_laptop_dataset.csv"))
print(f"✅ Loaded {len(df)} laptops")
print(f"   Columns: {list(df.columns)}")

# ── Clean columns ─────────────────────────────────────────────────────────────
df["RAM"] = pd.to_numeric(df["RAM"].astype(str).str.replace("GB","").str.strip(), errors="coerce")
df["Storage"] = pd.to_numeric(
    df["Storage"].astype(str).str.replace("GB","").str.replace("TB","000").str.strip(), errors="coerce"
)
df["Screen"] = df["Screen"].astype(str).str.extract(r"(\d+\.?\d*)").astype(float)
df["Price_LKR"] = pd.to_numeric(df["Final Price (LKR)"], errors="coerce")
df = df.dropna(subset=["Price_LKR", "RAM", "Storage"])
print(f"✅ After cleaning: {len(df)} laptops")

# ── Feature engineering ───────────────────────────────────────────────────────
df["has_discrete_gpu"] = df["GPU"].apply(
    lambda x: 0 if pd.isna(x) or str(x).strip() == "" or
    any(k in str(x).lower() for k in ["intel","integrated","uhd","iris"]) else 1
)

def cpu_tier(cpu):
    c = str(cpu).lower()
    if any(k in c for k in ["i9","ryzen 9","ultra 9"]): return 3
    if any(k in c for k in ["i7","ryzen 7","ultra 7"]): return 2
    if any(k in c for k in ["i5","ryzen 5","ultra 5"]): return 1
    return 0

df["cpu_tier"] = df["CPU"].apply(cpu_tier)

le_brand = LabelEncoder()
df["brand_encoded"] = le_brand.fit_transform(df["Brand"].fillna("Unknown"))

le_region = LabelEncoder()
if "Region" in df.columns:
    df["region_encoded"] = le_region.fit_transform(df["Region"].fillna("Colombo"))
else:
    df["region_encoded"] = 0

# Value score (target for RF)
df["value_score"] = (
    (df["RAM"] / df["Price_LKR"]) * 100_000 +
    (df["Storage"] / df["Price_LKR"]) * 10_000 +
    df["has_discrete_gpu"] * 0.5 +
    (df["cpu_tier"] / 3) * 0.5
)

FEATURES     = ["RAM", "Storage", "Price_LKR", "has_discrete_gpu", "brand_encoded", "cpu_tier"]
FEAT_KNN     = ["RAM", "Storage", "has_discrete_gpu", "brand_encoded", "cpu_tier", "region_encoded"]
FEAT_PRICE   = ["RAM", "Storage", "has_discrete_gpu", "brand_encoded", "cpu_tier"]

df[FEATURES + ["region_encoded"]] = df[FEATURES + ["region_encoded"]].fillna(0)

# ══════════════════════════════════════════════════════════════════════════════
# MODEL 1 — Random Forest Regressor (value score ranking)
# ══════════════════════════════════════════════════════════════════════════════
print("\n── Training Random Forest (value scoring) ──")
X_rf = df[FEATURES]
y_rf = df["value_score"]
X_train, X_test, y_train, y_test = train_test_split(X_rf, y_rf, test_size=0.2, random_state=42)

rf_model = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
rf_model.fit(X_train, y_train)
y_pred = rf_model.predict(X_test)
print(f"   MAE:  {mean_absolute_error(y_test, y_pred):.4f}")
print(f"   R²:   {r2_score(y_test, y_pred):.4f}")
print("   Feature importances:")
for feat, imp in zip(FEATURES, rf_model.feature_importances_):
    print(f"     {feat}: {imp:.4f}")

# ══════════════════════════════════════════════════════════════════════════════
# MODEL 2 — KNN Regressor (recommendation — find similar laptops)
# ══════════════════════════════════════════════════════════════════════════════
print("\n── Training KNN (recommendation) ──")
X_knn = df[FEAT_KNN]
y_knn = df["value_score"]

scaler_knn = StandardScaler()
X_knn_scaled = scaler_knn.fit_transform(X_knn)

X_train_k, X_test_k, y_train_k, y_test_k = train_test_split(
    X_knn_scaled, y_knn, test_size=0.2, random_state=42
)
knn_model = KNeighborsRegressor(n_neighbors=10, metric="euclidean", n_jobs=-1)
knn_model.fit(X_train_k, y_train_k)
y_pred_k = knn_model.predict(X_test_k)
print(f"   MAE:  {mean_absolute_error(y_test_k, y_pred_k):.4f}")
print(f"   R²:   {r2_score(y_test_k, y_pred_k):.4f}")

# ══════════════════════════════════════════════════════════════════════════════
# MODEL 3 — Ridge Regression (price prediction)
# ══════════════════════════════════════════════════════════════════════════════
print("\n── Training Ridge Regression (price prediction) ──")
X_price = df[FEAT_PRICE]
y_price = df["Price_LKR"]

scaler_price = StandardScaler()
X_price_scaled = scaler_price.fit_transform(X_price)

X_train_p, X_test_p, y_train_p, y_test_p = train_test_split(
    X_price_scaled, y_price, test_size=0.2, random_state=42
)
ridge_model = Ridge(alpha=1.0)
ridge_model.fit(X_train_p, y_train_p)
y_pred_p = ridge_model.predict(X_test_p)
print(f"   MAE:  LKR {mean_absolute_error(y_test_p, y_pred_p):,.0f}")
print(f"   R²:   {r2_score(y_test_p, y_pred_p):.4f}")

# ══════════════════════════════════════════════════════════════════════════════
# Save all models and encoders
# ══════════════════════════════════════════════════════════════════════════════
print("\n── Saving models ──")
models = {
    "model.pkl":           rf_model,
    "knn_model.pkl":       knn_model,
    "price_model.pkl":     ridge_model,
    "brand_encoder.pkl":   le_brand,
    "region_encoder.pkl":  le_region,
    "scaler_knn.pkl":      scaler_knn,
    "scaler_price.pkl":    scaler_price,
}
for filename, obj in models.items():
    path = os.path.join(BASE_DIR, filename)
    with open(path, "wb") as f:
        pickle.dump(obj, f)
    print(f"   ✅ Saved {filename}")

print("\n🎉 All models trained and saved successfully!")
print(f"   Random Forest  → value scoring & ranking")
print(f"   KNN            → recommendation (find similar laptops)")
print(f"   Ridge Regression → price prediction")
