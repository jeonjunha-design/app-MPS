from fastapi import FastAPI
from pydantic import BaseModel
import requests

app = FastAPI()

class UserPain(BaseModel):
    part: str
    level: int
    symptoms: str

@app.post("/get-routine")
async def get_routine(data: UserPain):
    # Ollama 로컬 주소 (맥에서도 동일하게 작동)
    url = "http://localhost:11434/api/generate"
    prompt = f"당신은 물리치료사입니다. {data.part} 부위 통증({data.level}/10), 증상: {data.symptoms}. 적절한 루틴을 JSON으로 작성해줘."
    
    payload = {"model": "llama3", "prompt": prompt, "stream": False}
    
    try:
        response = requests.post(url, json=payload)
        return {"routine": response.json().get('response', '응답 없음')}
    except Exception as e:
        return {"routine": f"오류 발생: {str(e)}"}
