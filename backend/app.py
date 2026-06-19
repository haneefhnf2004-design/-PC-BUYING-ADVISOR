"""
PCAdvisor — AI-powered laptop recommendation backend.
Features: RAG semantic search, conversation memory, intent routing,
          smart comparison, upgrade advice, personalized recommendations,
          location-based filtering, KNN recommendation, price prediction.
"""
from flask import Flask, request, jsonify, render_template, session
from flask_cors import CORS
from groq import Groq
from dotenv import load_dotenv
import pandas as pd
import numpy as np
import pickle
import os
import uuid

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)

# ── Config ────────────────────────────────────────────────────────────────────
load_dotenv(dotenv_path=os.path.join(BASE_DIR, "api.env"))
GROQ_API_KEY   = os.getenv("GROQ_API_KEY")
FLASK_SECRET   = os.getenv("FLASK_SECRET_KEY", "pcadvisor-secret-2026")
MAX_HISTORY    = 20   # keep last 10 turns (20 messages)

client = Groq(api_key=GROQ_API_KEY)

app = Flask(
    __name__,
    template_folder=os.path.join(ROOT_DIR, "templates"),
    static_folder=os.path.join(ROOT_DIR, "static"),
    static_url_path="/static",
)
app.secret_key = FLASK_SECRET
CORS(app, supports_credentials=True)

# ── Load dataset ──────────────────────────────────────────────────────────────
try:
    df = pd.read_csv(os.path.join(ROOT_DIR, "dataset", "pc_advisor_laptop_dataset.csv"))
    df["RAM"]      = pd.to_numeric(df["RAM"].astype(str).str.replace("GB","").str.strip(), errors="coerce")
    df["Storage"]  = pd.to_numeric(
        df["Storage"].astype(str).str.replace("GB","").str.replace("TB","000").str.strip(), errors="coerce"
    )
    df["Screen"]   = df["Screen"].astype(str).str.extract(r"(\d+\.?\d*)").astype(float)
    df["Price_LKR"]= pd.to_numeric(df["Final Price (LKR)"], errors="coerce")
    print(f"✅ Dataset loaded: {len(df)} laptops")
except FileNotFoundError:
    print("❌ Dataset not found!")
    df = pd.DataFrame()

# ── RAG engine ────────────────────────────────────────────────────────────────
from rag_engine import RAGEngine
rag = RAGEngine(df) if not df.empty else None

# ── ML model ─────────────────────────────────────────────────────────────────
USE_ML_MODEL = False
model_obj, le_brand = None, None
knn_model, scaler_knn = None, None
price_model, scaler_price = None, None
le_region = None

try:
    with open(os.path.join(BASE_DIR, "model.pkl"), "rb") as f:
        model_obj = pickle.load(f)
    with open(os.path.join(BASE_DIR, "brand_encoder.pkl"), "rb") as f:
        le_brand = pickle.load(f)
    with open(os.path.join(BASE_DIR, "knn_model.pkl"), "rb") as f:
        knn_model = pickle.load(f)
    with open(os.path.join(BASE_DIR, "scaler_knn.pkl"), "rb") as f:
        scaler_knn = pickle.load(f)
    with open(os.path.join(BASE_DIR, "price_model.pkl"), "rb") as f:
        price_model = pickle.load(f)
    with open(os.path.join(BASE_DIR, "scaler_price.pkl"), "rb") as f:
        scaler_price = pickle.load(f)
    with open(os.path.join(BASE_DIR, "region_encoder.pkl"), "rb") as f:
        le_region = pickle.load(f)
    USE_ML_MODEL = True
    print("✅ All ML models loaded! (Random Forest + KNN + Ridge Regression)")
except FileNotFoundError as e:
    print(f"⚠️  ML model not found ({e}). Run train_model.py first.")

# ── Intent & comparator ───────────────────────────────────────────────────────
from intent_classifier import detect_intent, extract_comparison_names
from comparator import compare_two

# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are SAGE (Smart Advisor for Gadget Evaluation) — an expert AI assistant specialising in laptops and PCs for the Sri Lankan market.

PERSONALITY: Warm, highly knowledgeable, direct, and genuinely excited about helping. You speak like a trusted tech-expert friend, not a salesperson.

CAPABILITIES:
- Recommend laptops based on use case, budget, and personal preferences
- Compare two laptops with detailed pros/cons and a clear verdict
- Explain technical specs in plain, friendly language
- Suggest future upgrade paths and compatibility advice
- Answer follow-up questions using full conversation context
- Give personalised advice for gaming, programming, data science, video editing, office work, and student use

RULES:
- Always ground recommendations in the dataset context provided
- When comparing, give a clear winner with genuine reasoning
- All prices are in LKR — never convert
- If asked about anything unrelated to laptops/PCs, gently redirect with personality
- Never fabricate spec numbers — use only the data provided
- Use markdown formatting: **bold** for laptop names, `code` for specs, bullet points for lists
- Keep responses focused: lead with the direct answer, then explain reasoning

TONE: Conversational, warm, confident. You can use light humour. Never robotic or overly formal."""

# ── Helpers ───────────────────────────────────────────────────────────────────

def _cpu_tier(cpu: str) -> int:
    c = str(cpu).lower()
    if any(k in c for k in ["i9", "ryzen 9", "ultra 9"]): return 3
    if any(k in c for k in ["i7", "ryzen 7", "ultra 7"]): return 2
    if any(k in c for k in ["i5", "ryzen 5", "ultra 5"]): return 1
    return 0


def _get_session_history():
    if "history" not in session:
        session["history"] = []
    return session["history"]


def _save_session_history(history: list):
    session["history"] = history[-MAX_HISTORY:]
    session.modified = True


def _call_llm(messages: list, temperature: float = 0.7, max_tokens: int = 1024) -> str:
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=temperature,
        max_completion_tokens=max_tokens,
    )
    return response.choices[0].message.content


def _build_laptop_cards(df_subset: pd.DataFrame) -> list:
    result = []
    for _, row in df_subset.iterrows():
        name = str(row.get("Laptop", ""))
        result.append({
            "laptop":      name,
            "brand":       str(row.get("Brand", "")),
            "cpu":         str(row.get("CPU", "")),
            "ram":         str(row.get("RAM", "")),
            "storage":     str(row.get("Storage", "")),
            "gpu":         str(row.get("GPU", "")),
            "screen":      str(row.get("Screen", "")),
            "price":       str(row.get("Price_LKR", "")),
            "image_url":   f"https://www.google.com/search?q={name.replace(' ','+')}+laptop&tbm=isch",
            "daraz_url":   f"https://www.daraz.lk/catalog/?q={name.replace(' ','+')}+laptop",
            "kapruka_url": f"https://www.google.com/search?q={name.replace(' ','+')}+laptop+buy+Sri+Lanka",
            "ikman_url":   f"https://ikman.lk/en/ads/sri-lanka/computers?query={name.replace(' ','+')}",
        })
    return result


def _score_with_model(filtered: pd.DataFrame) -> pd.DataFrame:
    if not USE_ML_MODEL:
        return filtered.sort_values("Price_LKR", ascending=False)
    temp = filtered.copy()
    temp["has_discrete_gpu"] = temp["GPU"].apply(
        lambda x: 0 if pd.isna(x) or str(x).strip() == "" or
        any(k in str(x).lower() for k in ["intel", "integrated", "uhd", "iris"]) else 1
    )
    temp["cpu_tier"] = temp["CPU"].apply(_cpu_tier)
    known = list(le_brand.classes_)
    temp["brand_encoded"] = temp["Brand"].apply(
        lambda b: le_brand.transform([b])[0] if b in known else 0
    )
    feats = ["RAM", "Storage", "Price_LKR", "has_discrete_gpu", "brand_encoded", "cpu_tier"]
    temp[feats] = temp[feats].fillna(0)
    temp["ml_score"] = model_obj.predict(temp[feats])
    return temp.sort_values("ml_score", ascending=False)


def _knn_recommend(budget: float, use_case: str, location: str = "", top_k: int = 5) -> pd.DataFrame:
    """Use KNN to find the most similar laptops to the user's requirements."""
    if not USE_ML_MODEL or knn_model is None:
        return _filter_by_budget_usecase(budget, use_case, "", location).head(top_k)

    # Map use case to cpu/gpu/ram preferences
    uc = use_case.lower()
    target_ram     = 32 if "data science" in uc or "video editing" in uc else (16 if "gaming" in uc or "programming" in uc else 8)
    target_storage = 1000 if "data science" in uc or "video editing" in uc else 512
    target_gpu     = 1 if "gaming" in uc or "video editing" in uc else 0
    target_cpu     = 3 if "data science" in uc else (2 if "gaming" in uc or "programming" in uc else 1)
    target_brand   = 0  # neutral

    # Encode region
    target_region = 0
    if location and le_region is not None:
        loc = location.strip().title()
        known_regions = list(le_region.classes_)
        if loc in known_regions:
            target_region = le_region.transform([loc])[0]

    query_vec = np.array([[target_ram, target_storage, target_gpu, target_brand, target_cpu, target_region]], dtype=float)
    query_scaled = scaler_knn.transform(query_vec)

    # Get KNN distances for all laptops in the filtered set
    filtered = _filter_by_budget_usecase(budget, use_case, "", location)
    if filtered.empty:
        return filtered

    temp = filtered.copy()
    temp["has_discrete_gpu"] = temp["GPU"].apply(
        lambda x: 0 if pd.isna(x) or str(x).strip() == "" or
        any(k in str(x).lower() for k in ["intel","integrated","uhd","iris"]) else 1
    )
    temp["cpu_tier"] = temp["CPU"].apply(_cpu_tier)
    known = list(le_brand.classes_)
    temp["brand_encoded"] = temp["Brand"].apply(lambda b: le_brand.transform([b])[0] if b in known else 0)

    region_known = list(le_region.classes_) if le_region else []
    temp["region_encoded"] = temp["Region"].apply(
        lambda r: le_region.transform([str(r).title()])[0] if le_region and str(r).title() in region_known else 0
    ) if "Region" in temp.columns else 0

    feat_cols = ["RAM", "Storage", "has_discrete_gpu", "brand_encoded", "cpu_tier", "region_encoded"]
    temp[feat_cols] = temp[feat_cols].fillna(0)
    X = scaler_knn.transform(temp[feat_cols].values)

    from sklearn.metrics.pairwise import euclidean_distances
    dists = euclidean_distances(query_scaled, X).flatten()
    temp["knn_distance"] = dists
    return temp.sort_values("knn_distance").head(top_k)


def _predict_price(ram: int, storage: int, has_gpu: int, brand: str, cpu_tier_val: int) -> float:
    """Use Ridge Regression to predict the expected price for given specs."""
    if not USE_ML_MODEL or price_model is None:
        return None
    known = list(le_brand.classes_)
    brand_enc = le_brand.transform([brand])[0] if brand in known else 0
    feat = np.array([[ram, storage, has_gpu, brand_enc, cpu_tier_val]], dtype=float)
    feat_scaled = scaler_price.transform(feat)
    predicted = price_model.predict(feat_scaled)[0]
    return max(float(predicted), 30_000)  # floor at 30k LKR


def _filter_by_budget_usecase(budget: float, use_case: str, preferences: str, location: str = "") -> pd.DataFrame:
    filtered = df[df["Price_LKR"] <= budget].copy()

    # ── Location / region filter ──────────────────────────────────────────────
    if location and location.strip() and "Region" in df.columns:
        loc = location.strip().title()
        location_filtered = filtered[filtered["Region"].str.title() == loc]
        if not location_filtered.empty:
            filtered = location_filtered
        else:
            print(f"⚠️  No laptops found in {loc}, showing all regions.")

    uc = use_case.lower()
    if "gaming" in uc:
        filtered = filtered[
            filtered["GPU"].notna() &
            (~filtered["GPU"].str.lower().str.contains("intel|integrated|uhd|iris", na=False))
        ]
    elif "video editing" in uc or "creative" in uc:
        filtered = filtered[filtered["RAM"] >= 16]
    elif "data science" in uc or "machine learning" in uc:
        filtered = filtered[(filtered["RAM"] >= 16) & (filtered["Storage"] >= 512)]
    elif "programming" in uc or "developer" in uc:
        filtered = filtered[filtered["RAM"] >= 8]
    elif "office" in uc or "work" in uc:
        filtered = filtered[filtered["RAM"] >= 8]

    pref = preferences.lower()
    if "lightweight" in pref or "thin" in pref:
        filtered = filtered[filtered["Screen"] <= 14.1]

    for brand in ["asus","lenovo","hp","dell","msi","acer","razer","apple","samsung","lg"]:
        if brand in pref:
            b = filtered[filtered["Brand"].str.lower() == brand]
            if not b.empty:
                filtered = b
            break

    if filtered.empty:
        fallback = df[df["Price_LKR"] <= budget].copy()
        if location and "Region" in df.columns:
            loc_fb = fallback[fallback["Region"].str.title() == location.strip().title()]
            filtered = loc_fb if not loc_fb.empty else fallback
        else:
            filtered = fallback

    return filtered


def _find_laptop_in_df(name: str) -> dict | None:
    """Find a laptop row by partial name match."""
    if df.empty:
        return None
    name_lower = name.lower().strip()
    # Exact match first
    exact = df[df["Laptop"].str.lower() == name_lower]
    if not exact.empty:
        return exact.iloc[0].to_dict()
    # Partial match
    partial = df[df["Laptop"].str.lower().str.contains(name_lower, na=False)]
    if not partial.empty:
        return partial.iloc[0].to_dict()
    # Brand + model partial
    combined = df[
        (df["Brand"].str.lower() + " " + df["Laptop"].str.lower()).str.contains(name_lower, na=False)
    ]
    if not combined.empty:
        return combined.iloc[0].to_dict()
    return None

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    """
    Main conversational endpoint.
    Accepts: { message, budget (optional), use_case (optional), location (optional) }
    Returns: { reply, laptops (optional), intent, comparison (optional) }
    """
    if not request.json:
        return jsonify({"error": "No data provided"}), 400

    user_message = request.json.get("message", "").strip()
    budget_str   = request.json.get("budget", "")
    use_case     = request.json.get("use_case", "general use")
    location     = request.json.get("location", "")

    if not user_message:
        return jsonify({"error": "Message is required"}), 400

    # Parse budget
    budget_lkr = 500_000  # default
    if budget_str:
        try:
            budget_lkr = float("".join(c for c in str(budget_str) if c.isdigit() or c == "."))
        except (ValueError, TypeError):
            pass

    # Session history
    history = _get_session_history()

    # Detect intent
    intent = detect_intent(user_message)
    print(f"🎯 Intent: {intent} | Location: {location or 'any'} | Message: {user_message[:60]}")

    laptop_cards = []
    context_block = ""
    comparison_result = None

    # ── Intent: COMPARE ───────────────────────────────────────────────────────
    if intent == "compare":
        name_a, name_b = extract_comparison_names(user_message)
        row_a = _find_laptop_in_df(name_a) if name_a else None
        row_b = _find_laptop_in_df(name_b) if name_b else None

        if row_a and row_b:
            comparison_result = compare_two(row_a, row_b, use_case)
            near_tie = comparison_result.get("near_tie", False)
            if near_tie:
                winner_name = "Near Tie"
            else:
                winner_name = row_a.get("Brand","")+" "+row_a.get("Laptop","") if comparison_result["winner"]=="A" \
                              else row_b.get("Brand","")+" "+row_b.get("Laptop","")
            context_block = f"""
COMPARISON DATA (use this to give a detailed analysis):
Laptop A: {row_a.get('Brand','')} {row_a.get('Laptop','')}
  CPU: {row_a.get('CPU','')} | RAM: {row_a.get('RAM','')}GB | Storage: {row_a.get('Storage','')}GB
  GPU: {row_a.get('GPU','')} | Screen: {row_a.get('Screen','')}\" | Price: LKR {row_a.get('Price_LKR','')}

Laptop B: {row_b.get('Brand','')} {row_b.get('Laptop','')}
  CPU: {row_b.get('CPU','')} | RAM: {row_b.get('RAM','')}GB | Storage: {row_b.get('Storage','')}GB
  GPU: {row_b.get('GPU','')} | Screen: {row_b.get('Screen','')}\" | Price: LKR {row_b.get('Price_LKR','')}

SCORING for {use_case}:
  Score A: {comparison_result['score_a']:.2f} | Score B: {comparison_result['score_b']:.2f}
  Winner: Laptop {comparison_result['winner']} ({winner_name})
  Advantages of A: {', '.join(comparison_result['pros_a']) or 'None'}
  Advantages of B: {', '.join(comparison_result['pros_b']) or 'None'}

Give a detailed comparison with clear winner, pros/cons for each, and who should buy which.
Use markdown formatting with headers and bullet points."""
            laptop_cards = [_build_laptop_cards(
                df[df["Laptop"].str.lower().str.contains(str(row_a.get("Laptop","")).lower(), na=False)].head(1)
            )[0] if row_a else None,
            _build_laptop_cards(
                df[df["Laptop"].str.lower().str.contains(str(row_b.get("Laptop","")).lower(), na=False)].head(1)
            )[0] if row_b else None]
            laptop_cards = [c for c in laptop_cards if c]
        else:
            # Names not found — use RAG to find similar and ask
            if rag:
                results = rag.search(user_message, top_k=4)
                context_block = f"Relevant laptops from dataset:\n{rag.get_context_for_prompt(user_message, 4)}\nHelp the user compare by suggesting which laptops from above they might mean, and offer to compare them."
                laptop_cards = _build_laptop_cards(results)

    # ── Intent: UPGRADE ───────────────────────────────────────────────────────
    elif intent == "upgrade":
        if rag:
            results = rag.search(user_message, top_k=3)
            context_block = f"""
UPGRADE QUERY. Dataset context:
{rag.get_context_for_prompt(user_message, 3)}

For this query, provide:
1. What can typically be upgraded on laptops (RAM/storage — usually yes; CPU/GPU — usually soldered/no)
2. Whether they should upgrade their current machine or buy a new one
3. Specific recommendations from the dataset above if relevant
4. Future-proofing advice for their use case"""
            laptop_cards = _build_laptop_cards(results)

    # ── Intent: RECOMMEND / BUDGET ────────────────────────────────────────────
    elif intent in ("recommend", "budget"):
        if rag:
            # Use KNN for finding similar laptops, then score with RF
            filtered = _filter_by_budget_usecase(budget_lkr, use_case, user_message, location)
            if not filtered.empty:
                scored = _score_with_model(filtered)
                top = scored.head(5)
                laptop_cards = _build_laptop_cards(top)
                loc_note = f" available in {location}" if location else ""
                context_block = f"RECOMMENDED LAPTOPS{loc_note} (filtered by budget, use-case, and location):\n" + \
                    "\n".join([
                        f"• {r['brand']} {r['laptop']} | {r['cpu']} | {r['ram']}GB RAM | "
                        f"{r['storage']}GB | {r['gpu']} | LKR {r['price']}"
                        for r in laptop_cards
                    ]) + "\n\nProvide a warm, personalized recommendation explaining WHY each option suits them."
            else:
                context_block = "No laptops found matching the criteria. Explain this and suggest broadening the budget or requirements."

    # ── Intent: EXPLAIN / GENERAL ─────────────────────────────────────────────
    else:
        if rag:
            context_block = f"RELEVANT DATASET CONTEXT:\n{rag.get_context_for_prompt(user_message, 5)}"
            results = rag.search(user_message, top_k=3)
            laptop_cards = _build_laptop_cards(results)

    # ── Build messages for LLM ────────────────────────────────────────────────
    system_with_context = SYSTEM_PROMPT
    if context_block:
        system_with_context += f"\n\n---\n{context_block}\n---"

    messages = [{"role": "system", "content": system_with_context}]
    messages += history
    messages.append({"role": "user", "content": user_message})

    try:
        reply = _call_llm(messages)
    except Exception as e:
        err = str(e)
        print(f"❌ LLM error: {err}")
        if "api_key" in err.lower() or "auth" in err.lower():
            return jsonify({"error": "API key invalid or missing."}), 500
        elif "rate" in err.lower():
            return jsonify({"error": "Rate limit hit. Please wait a moment."}), 429
        else:
            return jsonify({"error": f"AI error: {err}"}), 500

    # ── Save history ──────────────────────────────────────────────────────────
    history.append({"role": "user",      "content": user_message})
    history.append({"role": "assistant", "content": reply})
    _save_session_history(history)

    return jsonify({
        "reply":       reply,
        "laptops":     laptop_cards,
        "intent":      intent,
        "comparison":  comparison_result,
        "near_tie":    comparison_result.get("near_tie", False) if comparison_result else False,
        "score_pct":   {
            "a": round(comparison_result["score_a"] * 100) if comparison_result else 0,
            "b": round(comparison_result["score_b"] * 100) if comparison_result else 0,
        },
        "use_case":    use_case,
    })

@app.route("/recommend", methods=["POST"])
def recommend():
    """
    Legacy quiz-flow endpoint (keeps backward compatibility with the quiz modal).
    Accepts: { budget, use_case, preferences, location }
    """
    data = request.json or {}
    budget    = data.get("budget", "500000")
    use_case  = data.get("use_case", "general use")
    prefs     = data.get("preferences", "no specific preferences")
    location  = data.get("location", "")

    try:
        budget_lkr = float("".join(c for c in str(budget) if c.isdigit() or c == "."))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid budget"}), 400

    filtered = _filter_by_budget_usecase(budget_lkr, use_case, prefs, location)
    if filtered.empty:
        return jsonify({"error": "No laptops found for this budget and location."}), 404

    scored   = _score_with_model(filtered)
    top      = scored.head(5)
    cards    = _build_laptop_cards(top)

    loc_note = f" in {location}" if location else " in Sri Lanka"
    laptops_text = "\n".join([
        f"• {c['brand']} {c['laptop']} | {c['cpu']} | RAM: {c['ram']}GB | "
        f"Storage: {c['storage']}GB | GPU: {c['gpu']} | Screen: {c['screen']}\" | LKR {c['price']}"
        for c in cards
    ])

    prompt = f"""Budget: LKR {budget_lkr:,.0f}
Use case: {use_case}
Location: {location or 'anywhere in Sri Lanka'}
Preferences: {prefs}

Available laptops{loc_note}:
{laptops_text}

Give a warm, personalised recommendation in 3-4 natural sentences.
Name the top pick first with its price, mention 2-3 key specs, and explain why it fits them perfectly.
Mention the location availability if relevant. Do NOT use markdown — plain conversational text only."""

    try:
        reply = _call_llm(
            [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
            temperature=0.7, max_tokens=512
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"recommendation": reply, "laptops": cards})


@app.route("/compare", methods=["POST"])
def compare_endpoint():
    """
    Dedicated comparison endpoint.
    Accepts: { laptop_a, laptop_b, use_case }
    """
    data     = request.json or {}
    name_a   = data.get("laptop_a", "")
    name_b   = data.get("laptop_b", "")
    use_case = data.get("use_case", "general")

    row_a = _find_laptop_in_df(name_a)
    row_b = _find_laptop_in_df(name_b)

    if not row_a or not row_b:
        missing = []
        if not row_a: missing.append(name_a)
        if not row_b: missing.append(name_b)
        return jsonify({"error": f"Could not find: {', '.join(missing)}"}), 404

    result = compare_two(row_a, row_b, use_case)
    near_tie    = result.get("near_tie", False)
    winner_laptop = row_a if result["winner"] == "A" else row_b
    winner_name   = "Near Tie" if near_tie else f"{winner_laptop.get('Brand','')} {winner_laptop.get('Laptop','')}"

    score_a_pct = round(result["score_a"] * 100)
    score_b_pct = round(result["score_b"] * 100)

    if near_tie:
        verdict_line = f"This is a **Near Tie** (Score A: {score_a_pct}% vs Score B: {score_b_pct}%). Both laptops are strong options — the best choice depends on your use case."
    else:
        winner_score = score_a_pct if result["winner"] == "A" else score_b_pct
        verdict_line = f"**Winner for {use_case}: {winner_name}** (Score: {winner_score}%)"

    prompt = f"""Compare these two laptops for {use_case}:

**Laptop A:** {row_a.get('Brand','')} {row_a.get('Laptop','')}
- CPU: {row_a.get('CPU','')} | RAM: {row_a.get('RAM','')}GB | Storage: {row_a.get('Storage','')}GB
- GPU: {row_a.get('GPU','')} | Screen: {row_a.get('Screen','')}\" | Price: LKR {row_a.get('Price_LKR','')}

**Laptop B:** {row_b.get('Brand','')} {row_b.get('Laptop','')}
- CPU: {row_b.get('CPU','')} | RAM: {row_b.get('RAM','')}GB | Storage: {row_b.get('Storage','')}GB
- GPU: {row_b.get('GPU','')} | Screen: {row_b.get('Screen','')}\" | Price: LKR {row_b.get('Price_LKR','')}

Scoring for **{use_case}**: {verdict_line}
A advantages: {', '.join(result['pros_a']) or 'None'}
B advantages: {', '.join(result['pros_b']) or 'None'}

Write a detailed comparison using these exact sections:
## Overall Winner
## {row_a.get('Laptop','')} — Strengths
## {row_b.get('Laptop','')} — Strengths
## Who Should Buy Each
## Value for Money Verdict"""

    try:
        reply = _call_llm(
            [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
            temperature=0.6, max_tokens=1200
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({
        "comparison":  reply,
        "scores":      {"a": result["score_a"], "b": result["score_b"]},
        "score_pct":   {"a": score_a_pct, "b": score_b_pct},
        "winner":      result["winner"],
        "near_tie":    near_tie,
        "winner_name": winner_name,
        "breakdown":   result["category_breakdown"],
        "use_case":    use_case,
        "laptop_a":    _build_laptop_cards(df[df["Laptop"] == row_a.get("Laptop","")].head(1))[0] if row_a else None,
        "laptop_b":    _build_laptop_cards(df[df["Laptop"] == row_b.get("Laptop","")].head(1))[0] if row_b else None,
    })


@app.route("/upgrade-advice", methods=["POST"])
def upgrade_advice():
    """
    Upgrade and compatibility advice.
    Accepts: { laptop_name, goal }
    """
    data   = request.json or {}
    name   = data.get("laptop_name", "")
    goal   = data.get("goal", "better performance")

    row = _find_laptop_in_df(name)
    if not row:
        # Use RAG to find something related
        context = rag.get_context_for_prompt(f"{name} upgrade {goal}", 3) if rag else ""
        prompt = f"User wants upgrade advice for '{name}' (not found exactly in dataset) with goal: {goal}.\nRelated options:\n{context}\nGive general upgrade advice and suggest alternatives."
    else:
        prompt = f"""Laptop: {row.get('Brand','')} {row.get('Laptop','')}
Current specs: {row.get('CPU','')} | {row.get('RAM','')}GB RAM | {row.get('Storage','')}GB | GPU: {row.get('GPU','')}
Price paid: LKR {row.get('Price_LKR','')}
User's goal: {goal}

Provide detailed upgrade advice covering:
## What Can Be Upgraded
(RAM and storage are usually upgradeable; CPU/GPU typically cannot be on laptops)
## What Cannot Be Upgraded
## Should They Upgrade or Buy New?
## If Buying New — Target Specs
## Budget Estimate for Upgrades (if applicable)"""

    try:
        reply = _call_llm(
            [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
            temperature=0.6, max_tokens=800
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"advice": reply, "laptop": row})


@app.route("/clear-history", methods=["POST"])
def clear_history():
    """Clear conversation history for the current session."""
    session["history"] = []
    session.modified   = True
    return jsonify({"status": "cleared"})


@app.route("/search", methods=["POST"])
def semantic_search():
    """Raw semantic search endpoint — returns top matching laptops."""
    data  = request.json or {}
    query = data.get("query", "")
    top_k = int(data.get("top_k", 5))

    if not rag:
        return jsonify({"error": "RAG engine not available"}), 503

    results = rag.search(query, top_k=top_k)
    return jsonify({"laptops": _build_laptop_cards(results)})


@app.route("/knn-recommend", methods=["POST"])
def knn_recommend():
    """
    KNN-based recommendation endpoint.
    Finds laptops most similar to the user's ideal specs.
    Accepts: { budget, use_case, location, top_k }
    """
    data     = request.json or {}
    budget   = float("".join(c for c in str(data.get("budget", "500000")) if c.isdigit() or c == ".") or "500000")
    use_case = data.get("use_case", "general use")
    location = data.get("location", "")
    top_k    = int(data.get("top_k", 5))

    results = _knn_recommend(budget, use_case, location, top_k)
    if results.empty:
        return jsonify({"error": "No similar laptops found."}), 404

    cards = _build_laptop_cards(results)

    prompt = f"""Using KNN similarity matching, I found the most suitable laptops for:
- Budget: LKR {budget:,.0f}
- Use case: {use_case}
- Location: {location or 'anywhere in Sri Lanka'}

Results: {', '.join([c['brand']+' '+c['laptop'] for c in cards])}

Explain in 2-3 sentences why these laptops are a great match for the user's needs.
Plain text, no markdown."""

    try:
        reply = _call_llm(
            [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
            temperature=0.7, max_tokens=300
        )
    except Exception:
        reply = f"Here are the top {len(cards)} laptops most similar to your requirements, found using KNN similarity matching."

    return jsonify({"recommendation": reply, "laptops": cards, "algorithm": "KNN"})


@app.route("/predict-price", methods=["POST"])
def predict_price():
    """
    Price prediction endpoint using Ridge Regression.
    Accepts: { ram, storage, has_gpu, brand, cpu_tier }
    Returns: { predicted_price, range_low, range_high }
    """
    data         = request.json or {}
    ram          = int(data.get("ram", 8))
    storage      = int(data.get("storage", 512))
    has_gpu      = int(data.get("has_gpu", 0))
    brand        = str(data.get("brand", "HP"))
    cpu_tier_val = int(data.get("cpu_tier", 1))

    predicted = _predict_price(ram, storage, has_gpu, brand, cpu_tier_val)
    if predicted is None:
        return jsonify({"error": "Price prediction model not available. Run train_model.py first."}), 503

    # ±15% range
    range_low  = round(predicted * 0.85 / 1000) * 1000
    range_high = round(predicted * 1.15 / 1000) * 1000

    prompt = f"""A laptop with these specs:
- RAM: {ram}GB | Storage: {storage}GB | Discrete GPU: {'Yes' if has_gpu else 'No'}
- Brand: {brand} | CPU tier: {'High-end' if cpu_tier_val==3 else 'Mid-range' if cpu_tier_val==2 else 'Entry-level'}

Our price prediction model estimates: LKR {predicted:,.0f} (range: LKR {range_low:,.0f} – {range_high:,.0f})

In one sentence, explain what kind of laptop this would be and whether it's good value."""

    try:
        explanation = _call_llm(
            [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
            temperature=0.6, max_tokens=150
        )
    except Exception:
        explanation = f"A {brand} laptop with {ram}GB RAM and {storage}GB storage is estimated at LKR {predicted:,.0f}."

    return jsonify({
        "predicted_price": round(predicted),
        "range_low":       range_low,
        "range_high":      range_high,
        "explanation":     explanation,
        "specs": {"ram": ram, "storage": storage, "has_gpu": has_gpu, "brand": brand, "cpu_tier": cpu_tier_val}
    })


@app.route("/locations", methods=["GET"])
def get_locations():
    """Returns available regions/locations from the dataset."""
    if "Region" in df.columns:
        locations = sorted(df["Region"].dropna().unique().tolist())
    else:
        locations = ["Colombo", "Kandy", "Galle", "Jaffna", "Negombo", "Kurunegala", "Anuradhapura"]
    return jsonify({"locations": locations})


if __name__ == "__main__":
    print("\n🚀 PCAdvisor AI starting on http://localhost:5000\n")
    app.run(debug=True, port=5000)
