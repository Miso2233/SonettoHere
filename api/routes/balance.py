"""DeepSeek 余额查询 — 从 ProviderManager 获取凭据"""

import httpx
from fastapi import APIRouter, HTTPException, Request

router = APIRouter()

DEEPSEEK_BALANCE_URL = "https://api.deepseek.com/user/balance"


def _find_deepseek_api_key(request: Request) -> str:
    """在已配置的 provider 中查找 DeepSeek API key。

    通过 base_url 中是否包含 deepseek.com 来判断，
    不依赖用户填写的 id/label 名称。
    """
    mgr = getattr(request.app.state, "provider_manager", None)
    if mgr is None:
        raise HTTPException(status_code=400, detail="Provider manager not initialized")

    for config in mgr.list_configs():
        if not config.api_key:
            continue
        base = (config.base_url or "").lower()
        if "deepseek.com" in base:
            return config.api_key

    raise HTTPException(
        status_code=400,
        detail="DeepSeek provider not configured. Add one via the providers panel.",
    )


@router.get("/deepseek-balance")
async def get_deepseek_balance(request: Request) -> dict:
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
