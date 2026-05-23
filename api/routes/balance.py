"""DeepSeek 余额查询"""

import httpx
from fastapi import APIRouter, HTTPException

from config.settings import get_settings

router = APIRouter()

DEEPSEEK_BALANCE_URL = "https://api.deepseek.com/user/balance"

@router.get("/deepseek-balance")
async def get_deepseek_balance():
    settings = get_settings()
    if not settings.deepseek_api_key:
        raise HTTPException(status_code=400, detail="DeepSeek API key not set")
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {settings.deepseek_api_key}",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(DEEPSEEK_BALANCE_URL, headers=headers)
            data = response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="DeepSeek API timeout")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=500, detail=f"DeepSeek API error:{e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DeepSeek API error:{e}")
    return data

