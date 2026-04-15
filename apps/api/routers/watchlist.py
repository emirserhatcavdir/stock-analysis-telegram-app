"""Watchlist endpoints for the Mini App."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from apps.api.deps import get_chat_watchlist, load_watch_store
from apps.api.schemas import MutationResponse, WatchlistAddRequest, WatchlistRemoveRequest, WatchlistResponse
from stock_bot.analysis import normalize_symbol
from stock_bot.data_manager import add_to_watchlist, remove_from_watchlist

router = APIRouter(prefix="/api", tags=["watchlist"])


@router.get("/watchlist", response_model=WatchlistResponse)
def get_watchlist(user_id: int | None = Query(default=None), chat_id: int | None = Query(default=None)) -> WatchlistResponse:
    resolved_id = user_id if user_id is not None else chat_id
    if resolved_id is not None:
        symbols = get_chat_watchlist(resolved_id)
        return WatchlistResponse(chat_id=resolved_id, symbols=symbols)

    store = load_watch_store()
    normalized: dict[str, list[str]] = {}
    if isinstance(store, dict):
        for key in sorted(store.keys()):
            try:
                cid = int(key)
            except (TypeError, ValueError):
                continue
            normalized[str(cid)] = get_chat_watchlist(cid)
    return WatchlistResponse(watchlists=normalized)


@router.post("/watchlist/add", response_model=MutationResponse)
def add_watchlist_item(payload: WatchlistAddRequest) -> MutationResponse:
    normalized = normalize_symbol(payload.symbol)
    if not normalized:
        raise HTTPException(status_code=400, detail="symbol is required")

    user_id = payload.user_id or 0
    saved, added = add_to_watchlist(user_id, normalized)
    if not saved:
        raise HTTPException(status_code=400, detail="watchlist could not be saved")
    message = f"{normalized} added to watchlist" if added else f"{normalized} already in watchlist"
    return MutationResponse(ok=True, message=message, user_id=user_id)


@router.post("/watchlist/remove", response_model=MutationResponse)
def remove_watchlist_item(payload: WatchlistRemoveRequest) -> MutationResponse:
    normalized = normalize_symbol(payload.symbol)
    if not normalized:
        raise HTTPException(status_code=400, detail="symbol is required")

    user_id = payload.user_id or 0
    saved, removed = remove_from_watchlist(user_id, normalized)
    if not saved:
        raise HTTPException(status_code=400, detail="watchlist could not be saved")
    if not removed:
        raise HTTPException(status_code=404, detail=f"{normalized} not in watchlist")
    return MutationResponse(ok=True, message=f"{normalized} removed from watchlist", user_id=user_id)
