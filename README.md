# 🖥️ PCAdvisor — AI-Powered Laptop Recommendation System

An intelligent laptop recommendation web application built for the Sri Lankan market, powered by AI and machine learning.

---

## 👥 Team Members

| Name | Student ID |
|------|------------|
| J.A. Haneef | 03241130 |
| M.N.M. Zaatheer | 03241064 |
| K.M. Aatheeth | 03241012 |
| M.R.F. Rashidha | 03241163 |
| S.D.F. Safa | 03241128 |
| A.F. Afna | 03241172 |

---

## 📌 Project Overview

PCAdvisor is an AI-powered laptop recommendation system designed to help Sri Lankan users find the best laptop based on their needs and budget. The system combines natural language processing, machine learning, and a curated Sri Lanka-specific dataset with LKR pricing.

---

## 🚀 Features

- 🤖 **AI Chat Assistant** — Conversational recommendations using Groq API (Llama 3.3)
- 🔍 **RAG Semantic Search** — Retrieval-Augmented Generation for accurate answers
- 📊 **ML Ranking** — KNN + Random Forest model for value-score based recommendations
- 💬 **Intent Classification** — Smart routing between recommendation, comparison, and general Q&A
- 🔄 **Smart Comparison** — Side-by-side laptop comparison
- 📍 **Location-Based Filtering** — Region-aware recommendations for Sri Lanka
- 🛒 **Buy Links** — Auto-generated links to Daraz.lk and Kapruka.com
- 💡 **Upgrade Advisor** — Personalized upgrade path suggestions
- 🎙️ **SAGE Voice UI** — Sci-fi themed voice assistant interface

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, Flask |
| AI / LLM | Groq API (Llama 3.3-70b) |
| ML Model | scikit-learn (KNN, Random Forest) |
| Frontend | HTML, CSS, JavaScript |
| Dataset | Custom Sri Lanka laptop dataset (LKR pricing) |

---

## 📁 Project Structure

```
pc-buying-advisor/
├── backend/
│   ├── app.py               # Main Flask application
│   ├── comparator.py        # Laptop comparison logic
│   ├── intent_classifier.py # NLP intent routing
│   ├── rag_engine.py        # RAG semantic search
│   ├── train_model.py       # ML model training
│   └── api.env              # API keys (not committed)
├── dataset/
│   └── pc_advisor_laptop_dataset.csv
├── static/
│   ├── css/style.css
│   └── js/main.js
├── templates/
│   └── index.html
└── README.md
```

---

## ⚙️ Setup & Installation

### Prerequisites
- Python 3.10+
- Groq API Key

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/haneefhnf2004-design/PC_Buying_Advisor.git
cd PC_Buying_Advisor

# 2. Install dependencies
pip install flask flask-cors groq python-dotenv pandas numpy scikit-learn

# 3. Configure API keys
# Create backend/api.env and add:
# GROQ_API_KEY=your_groq_api_key_here

# 4. Train the ML model
python backend/train_model.py

# 5. Run the application
python backend/app.py
```

Visit `http://localhost:5000` in your browser.

---

## 📄 License

This project was developed as part of an academic coursework assignment.  
© 2026 Group CG01 — All rights reserved.
