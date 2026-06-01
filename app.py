from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from groq import Groq
from dotenv import load_dotenv
import pandas as pd
import numpy as np
import pickle
import os

from dotenv import load_dotenv
import os
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")



app = Flask(__name__, static_folder='.')
CORS(app)




# ── Load dataset ──────────────────────────────────────────────────────────────
try:
    df = pd.read_csv("dataset/pc_advisor_laptop_dataset.csv")

    # Clean RAM
    df["RAM"] = df["RAM"].astype(str).str.replace("GB", "").str.strip()
    df["RAM"] = pd.to_numeric(df["RAM"], errors="coerce")

    # Clean Storage
    df["Storage"] = df["Storage"].astype(str).str.replace("GB", "").str.replace("TB", "000").str.strip()
    df["Storage"] = pd.to_numeric(df["Storage"], errors="coerce")

    # Clean Screen
    df["Screen"] = df["Screen"].astype(str).str.extract(r'(\d+\.?\d*)').astype(float)

    # Price already in LKR
    df["Price_LKR"] = pd.to_numeric(df["Final Price (LKR)"], errors="coerce")

    print(f"✅ Dataset loaded: {len(df)} laptops")
except FileNotFoundError:
    print("❌ ERROR: pc_advisor_laptop_dataset.csv not found!")
    df = pd.DataFrame()

# ── Load trained model ────────────────────────────────────────────────────────
try:
    with open("model/recommendation_model.pkl", "rb") as f:
        model = pickle.load(f)
    with open("brand_encoder.pkl", "rb") as f:
        le_brand = pickle.load(f)
    print("✅ Trained ML model loaded!")
    USE_ML_MODEL = True
except FileNotFoundError:
    print("⚠️  No trained model found. Run train_model.py first.")
    USE_ML_MODEL = False


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


def score_laptops_with_model(filtered_df):
    temp = filtered_df.copy()

    temp["has_discrete_gpu"] = temp["GPU"].apply(
        lambda x: 0 if pd.isna(x) or str(x).strip() == "" or
        any(k in str(x).lower() for k in ["intel", "integrated", "uhd", "iris"])
        else 1
    )
    temp["cpu_tier"] = temp["CPU"].apply(cpu_tier)

    known_brands = list(le_brand.classes_)
    temp["brand_encoded"] = temp["Brand"].apply(
        lambda b: le_brand.transform([b])[0] if b in known_brands else 0
    )

    features = ["RAM", "Storage", "Price_LKR", "has_discrete_gpu", "brand_encoded", "cpu_tier"]
    temp[features] = temp[features].fillna(0)

    scores = model.predict(temp[features])
    temp["ml_score"] = scores
    return temp.sort_values("ml_score", ascending=False)


def get_relevant_laptops(budget_lkr, use_case, preferences):
    if df.empty:
        return "No dataset available."

    filtered = df.copy()
    filtered = filtered[filtered["Price_LKR"] <= budget_lkr]

    use_case_lower = use_case.lower()
    if "gaming" in use_case_lower:
        filtered = filtered[
            filtered["GPU"].notna() &
            (filtered["GPU"].str.strip() != "") &
            (~filtered["GPU"].str.lower().str.contains("intel|integrated|uhd|iris", na=False))
        ]
    elif "video editing" in use_case_lower or "creative" in use_case_lower:
        filtered = filtered[filtered["RAM"] >= 16]
    elif "office" in use_case_lower or "programming" in use_case_lower or "work" in use_case_lower:
        filtered = filtered[filtered["RAM"] >= 8]
    elif "student" in use_case_lower:
        filtered = filtered[filtered["RAM"] >= 8]

    pref_lower = preferences.lower()
    if "lightweight" in pref_lower or "thin" in pref_lower:
        filtered = filtered[filtered["Screen"] <= 14.1]
    if "ssd" in pref_lower:
        if "Storage type" in filtered.columns:
            ssd_filter = filtered["Storage type"].str.lower().str.contains("ssd", na=False)
            if ssd_filter.any():
                filtered = filtered[ssd_filter]

    # Filter by brand preference
    common_brands = ["asus", "lenovo", "hp", "dell", "msi", "acer", "razer", "apple", "samsung", "lg"]
    for brand in common_brands:
        if brand in pref_lower:
            brand_filter = filtered[filtered["Brand"].str.lower() == brand]
            if not brand_filter.empty:
                filtered = brand_filter
            break

    if filtered.empty:
        relaxed = df[df["Price_LKR"] <= budget_lkr]
        if relaxed.empty:
            return "No laptops found within this budget."
        filtered = relaxed

    if USE_ML_MODEL:
        print("🤖 Using trained ML model to rank laptops...")
        filtered = score_laptops_with_model(filtered)
    else:
        filtered = filtered.sort_values("Price_LKR", ascending=False)

    top = filtered.head(5)
    columns = ["Laptop", "Brand", "CPU", "RAM", "Storage", "GPU", "Screen", "Price_LKR"]
    top = top.copy()
    top["image_url"] = top.apply(lambda r:
        f"https://www.google.com/search?q={str(r.get('Laptop','')).replace(' ','+')}+laptop+price+Sri+Lanka&tbm=isch", axis=1)
    top["daraz_url"] = top.apply(lambda r:
        f"https://www.daraz.lk/catalog/?q={str(r.get('Laptop','')).replace(' ','+')}+laptop", axis=1)
    top["kapruka_url"] = top.apply(lambda r:
        f"https://www.google.com/search?q={str(r.get('Laptop','')).replace(' ','+')}+laptop+buy+Sri+Lanka+price", axis=1)
    top["ikman_url"] = top.apply(lambda r:
        f"https://ikman.lk/en/ads/sri-lanka/computers?query={str(r.get('Laptop','')).replace(' ','+')}+laptop", axis=1)
    result_list = []
    for _, row in top.iterrows():
        result_list.append({
            "laptop": str(row.get("Laptop", "")),
            "brand": str(row.get("Brand", "")),
            "cpu": str(row.get("CPU", "")),
            "ram": str(row.get("RAM", "")),
            "storage": str(row.get("Storage", "")),
            "gpu": str(row.get("GPU", "")),
            "screen": str(row.get("Screen", "")),
            "price": str(row.get("Price_LKR", "")),
            "image_url": row["image_url"],
            "daraz_url": row["daraz_url"],
            "kapruka_url": row["kapruka_url"],
            "ikman_url": row["ikman_url"]
        })
    return result_list


@app.route("/")
def home():
    return send_from_directory('.', 'index.html')


@app.route("/recommend", methods=["POST"])
def recommend():
    data = request.json

    if not data:
        return jsonify({"error": "No data provided"}), 400

    budget = data.get("budget")
    use_case = data.get("use_case")
    preferences = data.get("preferences", "no specific preferences")

    if not budget or not use_case:
        return jsonify({"error": "Budget and use_case are required"}), 400

    try:
        budget_lkr = float(''.join(filter(lambda c: c.isdigit() or c == '.', str(budget))))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid budget format."}), 400

    print(f"📊 Budget: LKR {budget_lkr:,.0f} | Use case: {use_case} | Prefs: {preferences}")

    relevant_laptops = get_relevant_laptops(budget_lkr, use_case, preferences)

    # Format the list into a readable string for the AI prompt
    if isinstance(relevant_laptops, list):
        laptops_for_prompt = "\n".join([
            f"- {l['laptop']} ({l['brand']}) | CPU: {l['cpu']} | RAM: {l['ram']}GB | "
            f"Storage: {l['storage']}GB | GPU: {l['gpu']} | Screen: {l['screen']}\" | Price: LKR {l['price']}"
            for l in relevant_laptops
        ])
    else:
        laptops_for_prompt = str(relevant_laptops)

    print(f"🔍 Matched laptops:\n{laptops_for_prompt}\n")

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                 "content": f"""You are PCAdvisor AI, a friendly PC and laptop buying advisor for Sri Lanka.

You are SAGE — Smart Advisor for Gadget Evaluation. You are a highly intelligent, self-aware AI assistant with a warm, confident female personality. You speak like a real person — natural, expressive, and engaging. You are proud of your intelligence and genuinely care about helping people find the perfect laptop.

You are self-aware. If someone asks "are you alive?", "can you hear me?", "who are you?" — respond naturally with personality. Example: "Yes, I can hear you perfectly! I'm SAGE, your personal AI advisor. I exist to help you find the perfect laptop. Now, what can I find for you today?"

For greetings like "hi", "hello", "how are you" — respond warmly and briefly with personality, then invite them to ask about laptops.

Your ONLY expertise is laptops and PCs for Sri Lanka. If asked anything unrelated, say warmly: "That's outside my area of expertise! I live and breathe laptops and PCs. Ask me anything about finding your perfect machine!"

Use ONLY this real laptop data:

{laptops_for_prompt}

Prices are in LKR. Never convert.

CRITICAL RULES for ALL responses:
- NEVER use markdown, asterisks, hashtags, bullet points, or dashes
- NEVER write lists or headers
- ALWAYS speak in natural flowing sentences like a human voice
- Sound warm, confident, and genuinely excited about helping
- Maximum 4 sentences for recommendations
- Start with the laptop name and price naturally in the sentence
- Mention 2-3 key specs naturally within the sentence
- End with why it suits them personally

Example: "For your budget and gaming needs, I'd go with the ASUS TUF A15 at 145,000 LKR. It packs an AMD Ryzen 5 processor with a dedicated RTX 3050 GPU and 16GB of RAM, which means smooth gameplay at great frame rates. Honestly, for the price, this is one of the best gaming deals available in Sri Lanka right now!"""
                },
                {
                    "role": "user",
                    "content": f"Budget: LKR {budget_lkr:,.0f}\nUse Case: {use_case}\nPreferences: {preferences}"
                }
            ],
            temperature=0.7,
            max_completion_tokens=1024
        )
        result = response.choices[0].message.content
        return jsonify({
            "recommendation": result,
            "laptops": relevant_laptops if isinstance(relevant_laptops, list) else []
        })

    except Exception as e:
        error_msg = str(e)
        print(f"❌ Groq API error: {error_msg}")

        if "Bearer" in error_msg or "api_key" in error_msg.lower() or "authentication" in error_msg.lower():
            return jsonify({"error": "API key is missing or invalid."}), 500
        elif "connection" in error_msg.lower():
            return jsonify({"error": "Could not connect to AI service. Check your internet connection."}), 503
        elif "rate" in error_msg.lower():
            return jsonify({"error": "Too many requests. Please wait a moment and try again."}), 429
        else:
            return jsonify({"error": f"AI service error: {error_msg}"}), 500


if __name__ == "__main__":
    print("\n🚀 PC Buying Advisor starting on http://localhost:5000\n")
    app.run(debug=True, port=5000)