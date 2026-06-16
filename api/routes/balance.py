"""DeepSeek 余额查询 — 从 ProviderManager 获取凭据"""

import httpx
from fastapi import APIRouter, HTTPException, Request

router = APIRouter()

DEEPSEEK_BALANCE_URL = "https://api.deepseek.com/user/balance"


def _find_deepseek_api_key(request: Request) -> str:
    """在已配置的 provider 中查找 DeepSeek API key。"""
    mgr = getattr(request.app.state, "provider_manager", None)
    if mgr is None:
        raise HTTPException(status_code=400, detail="Provider manager not initialized")

    for config in mgr.list_configs():
        lid = (config.id + config.label).lower()
        if "deepseek" in lid and config.api_key:
            return config.api_key

    raise HTTPException(status_code=400, detail="DeepSeek provider not configured. Add one via the providers panel.")


@router.get("/deepseek-balance")
async def get_deepseek_balance(request: Request):
    api_key = _find_deepseek_api_key(request)
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(DEEPSEEK_BALANCE_URL, headers=headers)
            data = response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="DeepSeek API timeout")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=500, detail=f"DeepSeek API error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DeepSeek API error: {e}")
    return data

