"""Dashboard-facing alert endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from schemas import AlertAddRequest, AlertRemoveRequest, AlertResponse, MutationResponse
from services.alert_service import add_advanced_alert, add_price_alert, get_alerts, remove_alert

router = APIRouter(tags=["alerts"])


@router.get("/alerts/{user_id}", response_model=AlertResponse)
@router.get("/api/alerts/{user_id}", response_model=AlertResponse)
def alerts(user_id: int) -> AlertResponse:
    return AlertResponse(**get_alerts(user_id))


@router.post("/alerts/{user_id}/add", response_model=MutationResponse)
@router.post("/api/alerts/{user_id}/add", response_model=MutationResponse)
def alerts_add(user_id: int, payload: AlertAddRequest) -> MutationResponse:
    alert_type = payload.alert_type.strip().lower()
    symbol = payload.symbol

    if alert_type == "price":
        if payload.side is None or payload.target is None:
            raise HTTPException(status_code=400, detail="price alert requires side and target")
        data = add_price_alert(user_id, symbol, payload.side, payload.target)
    else:
        rule = {
            "type": alert_type,
            "side": payload.side,
            "target": payload.target,
            "state": payload.state,
            "direction": payload.direction,
            "threshold": payload.threshold,
            "signal": payload.signal,
            "multiplier": payload.multiplier,
        }
        data = add_advanced_alert(user_id, symbol, rule)

    if not data["ok"]:
        raise HTTPException(status_code=400, detail=data["message"])
    return MutationResponse(ok=True, message=data["message"], user_id=user_id)


@router.post("/alerts/{user_id}/remove", response_model=MutationResponse)
@router.post("/api/alerts/{user_id}/remove", response_model=MutationResponse)
def alerts_remove(user_id: int, payload: AlertRemoveRequest) -> MutationResponse:
    data = remove_alert(user_id, payload.symbol, payload.alert_type, payload.side)
    if not data["ok"]:
        raise HTTPException(status_code=400, detail=data["message"])
    return MutationResponse(ok=True, message=data["message"], user_id=user_id)

