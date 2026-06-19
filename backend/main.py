from flask import Flask, request, jsonify
from advisor import get_recommendation

app = Flask(__name__)

@app.route("/")
def home():
    return "PC Buying Advisor API is running!"

@app.route("/recommend", methods=["POST"])
def recommend():
    data = request.json

    # Validate input
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    budget = data.get("budget")
    use_case = data.get("use_case")
    preferences = data.get("preferences", "no specific preferences")

    if not budget or not use_case:
        return jsonify({"error": "Budget and use_case are required"}), 400

    # Get AI recommendation
    result = get_recommendation(budget, use_case, preferences)

    return jsonify({
        "recommendation": result
    })

if __name__ == "__main__":
    app.run(debug=True, port=5000)