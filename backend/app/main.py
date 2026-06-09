from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI()

class LogEntry(BaseModel):
    type: str
    url: Optional[str]
    title: Optional[str]
    timestamp: float


@app.post('/api/v1/logs')
async def ingest(entries: List[LogEntry]):
    for e in entries:
        print('INGEST:', e.dict())
    return {'received': len(entries)}


if __name__ == '__main__':
    import uvicorn
    uvicorn.run('backend.app.main:app', host='127.0.0.1', port=8000, reload=True)
