from groq import Groq

client = Groq(api_key="your_groq_api_key_here")

def get_recommendation(budget, use_case, preferences):
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": """You are an expert PC buying advisor for Sri Lanka.
                Given the user's budget in LKR, use case, and preferences,
                recommend either a prebuilt PC or a custom build.
                
                Always include:
                - Component list (CPU, GPU, RAM, Storage, PSU)
                - Estimated price in LKR
                - Why it suits their use case
                - One alternative option"""
            },
            {
                "role": "user",
                "content": f"Budget: {budget}\nUse Case: {use_case}\nPreferences: {preferences}"
            }
        ]
    )
    return response.choices[0].message.content