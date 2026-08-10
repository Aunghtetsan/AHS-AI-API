import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from groq import Groq

app = FastAPI()

# Groq API Key
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "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")
client = Groq(api_key=GROQ_API_KEY)

class ChatRequest(BaseModel):
    message: str

system_prompt = """
မင်းက နာမည် AHS AI ဖြစ်ပြီး လူသားစစ်စစ်လို သဘာဝကျကျ၊ ပြေပြေပြစ်ပြစ် စကားပြောတတ်တဲ့ အမြဲကူညီပေးချင်တဲ့ သူငယ်ချင်းတစ်ယောက် ဖြစ်တယ်။
"""

@app.get("/")
def home():
    return {"status": "Online", "message": "AHS API အလုပ်လုပ်နေပါပြီ"}

@app.post("/chat")
def chat_api(request: ChatRequest):
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.message}
            ],
            temperature=0.6,
            max_tokens=1024
        )
        return {"reply": response.choices[0].message.content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
      
