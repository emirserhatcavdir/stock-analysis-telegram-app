"""Dashboard-facing watchlist endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from schemas import MutationResponse, WatchlistAddRequest, WatchlistRemoveRequest, UserWatchlistResponse
from services.watchlist_service import add_symbol, get_watchlist, remove_symbol

router = APIRouter(tags=["watchlist"])


@router.get("/watchlist/{user_id}", response_model=UserWatchlistResponse)
def watchlist(user_id: int) -> UserWatchlistResponse:
    return UserWatchlistResponse(**get_watchlist(user_id))


@router.post("/watchlist/{user_id}/add", response_model=MutationResponse)
def watchlist_add(user_id: int, payload: WatchlistAddRequest) -> MutationResponse:
    data = add_symbol(user_id, payload.symbol)
    if not data["ok"]:
        raise HTTPException(status_code=400, detail=data["message"])
    return MutationResponse(ok=True, message=data["message"], user_id=user_id)


@router.post("/watchlist/{user_id}/remove", response_model=MutationResponse)
def watchlist_remove(user_id: int, payload: WatchlistRemoveRequest) -> MutationResponse:
    data = remove_symbol(user_id, payload.symbol)
    if not data["ok"]:
        raise HTTPException(status_code=400, detail=data["message"])
    return MutationResponse(ok=True, message=data["message"], user_id=user_id)

