"""Dashboard-facing portfolio endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from apps.api.schemas import MutationResponse, PortfolioAddRequest, PortfolioRemoveRequest, UserPortfolioResponse
from apps.api.services.portfolio_service import add_position, get_portfolio, remove_position

router = APIRouter(tags=["portfolio"])


@router.get("/portfolio/{user_id}", response_model=UserPortfolioResponse)
def portfolio(user_id: int) -> UserPortfolioResponse:
    return UserPortfolioResponse(**get_portfolio(user_id))


@router.post("/portfolio/{user_id}/add", response_model=MutationResponse)
def portfolio_add(user_id: int, payload: PortfolioAddRequest) -> MutationResponse:
    data = add_position(user_id, payload.symbol, payload.shares, payload.buy_price)
    if not data["ok"]:
        raise HTTPException(status_code=400, detail=data["message"])
    return MutationResponse(ok=True, message=data["message"], user_id=user_id)


@router.post("/portfolio/{user_id}/remove", response_model=MutationResponse)
def portfolio_remove(user_id: int, payload: PortfolioRemoveRequest) -> MutationResponse:
    data = remove_position(user_id, payload.symbol)
    if not data["ok"]:
        raise HTTPException(status_code=400, detail=data["message"])
    return MutationResponse(ok=True, message=data["message"], user_id=user_id)

