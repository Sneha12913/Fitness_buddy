import os
import json
from flask import Flask, render_template, request, jsonify
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

INSTANCE_URL = os.getenv("ORCHESTRATE_INSTANCE_URL")
AGENT_ID = os.getenv("AGENT_ID")
API_KEY = os.getenv("IBM_API_KEY")

def get_auth_token():
    url = "https://iam.cloud.ibm.com/identity/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
        "apikey": API_KEY
    }
    try:
        res = requests.post(url, headers=headers, data=data)
        if res.status_code != 200:
            return None
        return res.json().get("access_token")
    except Exception:
        return None

@app.route("/")
def home():
    # This renders the external index.html file directly from the templates folder!
    return render_template("index.html")
@app.post("/api/chat")
def chat_with_fitness_buddy():
    user_text = request.json.get("text")
    token = get_auth_token()
    
    if not token:
        return jsonify({"reply": "Backend Error: IBM Key validation failed."}), 401
        
    api_route = f"{INSTANCE_URL}/v1/orchestrate/{AGENT_ID}/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream"  # Notice we are embracing the stream here!
    }
    
    body = {
        "messages": [
            {
                "role": "user",
                "content": user_text
            }
        ]
    }
    
    try:
        # Request with stream=True so Python captures chunk by chunk
        response = requests.post(api_route, headers=headers, json=body, stream=True)
        
        if response.status_code != 200:
            return jsonify({"reply": f"IBM Gateway Error ({response.status_code})"}), response.status_code

        full_reply = ""
        
        # Read the chunks as they stream down from IBM
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8').strip()
                if decoded_line.startswith("data:"):
                    json_str = decoded_line[5:].strip()
                    
                    # Skip empty keep-alive pings or terminal signs
                    if not json_str or json_str == "[DONE]":
                        continue
                        
                    try:
                        chunk_data = json.loads(json_str)
                        choices = chunk_data.get("choices", [])
                        if choices:
                            # Extract text chunk out of the delta property
                            delta_content = choices[0].get("delta", {}).get("content", "")
                            full_reply += delta_content
                    except Exception:
                        pass
                        
        if not full_reply:
            full_reply = "I received an empty response. Please try asking again!"

        return jsonify({"reply": full_reply})
        
    except Exception as e:
        return jsonify({"reply": f"Error handling response: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(port=5000, debug=True)