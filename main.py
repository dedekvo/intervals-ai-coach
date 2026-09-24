import os
import datetime
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI

app = FastAPI()

# Povolení CORS pro mobilní/webovou aplikaci
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

class UserCredentials(BaseModel):
    intervals_athlete_id: str
    intervals_api_key: str

@app.post("/analyze")
def analyze_training(creds: UserCredentials):
    athlete_id = creds.intervals_athlete_id.strip()
    api_key = creds.intervals_api_key.strip()

    # Spočítáme datum před 30 dny ve formátu YYYY-MM-DD
    oldest_date = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
    
    # Přidáme parametr oldest do URL
    url = f"https://intervals.icu/api/v1/athlete/{athlete_id}/activities?oldest={oldest_date}"
    
    print(f"Odesílám požadavek na: {url}")
    response = requests.get(url, auth=("API_KEY", api_key))
    
    if response.status_code != 200:
        print(f"CHYBA INTERVALS: Status {response.status_code}, Body: {response.text}")
        raise HTTPException(
            status_code=400, 
            detail=f"Intervals.icu chyba {response.status_code}: {response.text}"
        )
    
    activities = response.json()
    
    if not activities:
        return {"status": "success", "analysis": "Zatím nemáte v Intervals.icu za posledních 30 dní zaznamenané žádné aktivity."}
    
    recent_activities = activities[:7]
    
    data_summary = "Zde jsou poslední tréninkové aktivity sportovce:\n"
    for act in recent_activities:
        moving_time_min = round(act.get('moving_time', 0) / 60)
        data_summary += (
            f"- Datum: {act.get('start_date_local', 'N/A')[:10]}, "
            f"Název: {act.get('name', 'Bez názvu')}, "
            f"Typ: {act.get('type', 'N/A')}, "
            f"Doba: {moving_time_min} min, "
            f"TSS: {act.get('tss', 'N/A')}, "
            f"Prům. tep: {act.get('average_heartrate', 'N/A')} bpm, "
            f"Prům. výkon: {act.get('average_watts', 'N/A')} W\n"
        )

    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system", 
                    "content": "Jsi zkušený vytrvalostní trenér. Analyzuj data sportovce a poskytni mu věcnou zpětnou vazbu a doporučení."
                },
                {"role": "user", "content": data_summary}
            ]
        )
        return {"status": "success", "analysis": completion.choices[0].message.content}
    except Exception as e:
        print(f"CHYBA OPENAI: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))