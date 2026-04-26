from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests


BINANCE_EXCHANGE_INFO = "https://api.binance.com/api/v3/exchangeInfo"
BINANCE_KLINES = "https://api.binance.com/api/v3/klines"
REQUEST_TIMEOUT = 20
PREFERRED_QUOTES = ("USDT", "FDUSD", "USDC", "BTC", "ETH")


@dataclass
class KlinePoint:
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


def safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def ema(values: List[float], period: int) -> float:
    if not values:
        return 0.0
    if len(values) < period:
        return sum(values) / max(len(values), 1)

    multiplier = 2 / (period + 1)
    current = sum(values[:period]) / period
    for price in values[period:]:
        current = (price - current) * multiplier + current
    return current


def atr(klines: List[KlinePoint], period: int = 14) -> float:
    if len(klines) < 2:
        return 0.0

    trs: List[float] = []
    prev_close = klines[0].close
    for k in klines[1:]:
        tr = max(
            k.high - k.low,
            abs(k.high - prev_close),
            abs(k.low - prev_close),
        )
        trs.append(tr)
        prev_close = k.close

    if not trs:
        return 0.0

    if len(trs) < period:
        return sum(trs) / len(trs)

    recent = trs[-period:]
    return sum(recent) / len(recent)


def fetch_binance_spot_map() -> Tuple[Dict[str, List[str]], Optional[str]]:
    try:
        r = requests.get(
            BINANCE_EXCHANGE_INFO,
            params={"permissions": "SPOT"},
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()

        symbol_map: Dict[str, List[str]] = {}
        for s in data.get("symbols", []):
            if s.get("status") != "TRADING":
                continue

            base = (s.get("baseAsset") or "").upper()
            quote = (s.get("quoteAsset") or "").upper()
            symbol = s.get("symbol") or ""

            if not base or not quote or not symbol:
                continue
            if quote not in PREFERRED_QUOTES:
                continue

            symbol_map.setdefault(base, []).append(symbol)

        return symbol_map, None
    except Exception as e:
        return {}, str(e)


def choose_best_pair(symbols: List[str]) -> Optional[str]:
    if not symbols:
        return None

    priority = ["USDT", "FDUSD", "USDC", "BTC", "ETH"]
    for quote in priority:
        for s in symbols:
            if s.endswith(quote):
                return s
    return symbols[0]


def fetch_klines(pair: str, interval: str = "1h", limit: int = 120) -> List[KlinePoint]:
    r = requests.get(
        BINANCE_KLINES,
        params={"symbol": pair, "interval": interval, "limit": limit},
        timeout=REQUEST_TIMEOUT,
    )
    r.raise_for_status()
    rows = r.json()

    out: List[KlinePoint] = []
    for row in rows:
        out.append(
            KlinePoint(
                open_time=int(row[0]),
                open=safe_float(row[1]),
                high=safe_float(row[2]),
                low=safe_float(row[3]),
                close=safe_float(row[4]),
                volume=safe_float(row[5]),
            )
        )
    return out


def _nearest_levels(
    highs: List[float],
    lows: List[float],
    price: float,
    support_lookback: int,
    resistance_lookback: int,
) -> Tuple[float, float]:
    recent_lows = lows[-support_lookback:] if lows else []
    recent_highs = highs[-resistance_lookback:] if highs else []

    support = min(recent_lows) if recent_lows else price * 0.96
    resistance = max(recent_highs) if recent_highs else price * 1.04

    if support >= price:
        support = price * 0.97
    if resistance <= price:
        resistance = price * 1.03

    return support, resistance


def build_snr_from_klines(
    klines: List[KlinePoint],
    rules: Dict[str, Any],
) -> Dict[str, Any]:
    closes = [k.close for k in klines]
    highs = [k.high for k in klines]
    lows = [k.low for k in klines]
    volumes = [k.volume for k in klines]

    price = closes[-1] if closes else 0.0
    atr_value = atr(klines, int(rules.get("atr_period", 14)))
    ema_fast = ema(closes, int(rules.get("ema_fast", 20)))
    ema_slow = ema(closes, int(rules.get("ema_slow", 50)))

    support, resistance = _nearest_levels(
        highs,
        lows,
        price,
        int(rules.get("support_lookback", 24)),
        int(rules.get("resistance_lookback", 24)),
    )

    avg_vol = sum(volumes[-20:]) / max(len(volumes[-20:]), 1) if volumes else 0.0
    volume_ratio = (volumes[-1] / avg_vol) if avg_vol > 0 and volumes else 1.0

    if price > ema_fast > ema_slow:
        trend = "bullish"
    elif price < ema_fast < ema_slow:
        trend = "bearish"
    else:
        trend = "neutral"

    support_zone = [round(support, 6), round(support + atr_value * 0.35, 6)]
    resistance_zone = [round(max(resistance - atr_value * 0.35, price), 6), round(resistance, 6)]

    entry_aggressive = round(support + atr_value * 0.15, 6)
    entry_confirmation = round(max(price, resistance + atr_value * 0.05), 6)
    invalidation = round(max(support - atr_value * 0.8, 0), 6)
    tp1 = round(resistance, 6)
    tp2 = round(resistance + max((resistance - support) * 0.75, atr_value * 1.2), 6)

    rr = 0.0
    risk_unit = max(price - invalidation, atr_value * 0.5, 1e-9)
    reward_unit = max(tp1 - price, 0.0)
    rr = round(reward_unit / risk_unit, 2)

    history = []
    limit = int(rules.get("history_limit", 40))
    for idx, k in enumerate(klines[-limit:]):
        history.append({"d": str(idx + 1), "score": round(k.close, 4)})

    return {
        "trend": trend,
        "price": round(price, 6),
        "supportZone": support_zone,
        "resistanceZone": resistance_zone,
        "entryAggressive": entry_aggressive,
        "entryConfirmation": entry_confirmation,
        "breakoutLevel": round(resistance + atr_value * 0.03, 6),
        "invalidation": invalidation,
        "tp1": tp1,
        "tp2": tp2,
        "rr": rr,
        "atr": round(atr_value, 6),
        "emaFast": round(ema_fast, 6),
        "emaSlow": round(ema_slow, 6),
        "volumeRatio": round(volume_ratio, 2),
        "history": history,
    }


def build_fallback_snr(
    price: float,
    impact_pct: float,
) -> Dict[str, Any]:
    pad = max(price * 0.03, price * max(impact_pct / 100.0, 0.01))
    support = max(price - pad, 0)
    resistance = price + pad

    return {
        "trend": "neutral",
        "price": round(price, 6),
        "supportZone": [round(max(support * 0.995, 0), 6), round(support, 6)],
        "resistanceZone": [round(resistance, 6), round(resistance * 1.01, 6)],
        "entryAggressive": round(support, 6),
        "entryConfirmation": round(price * 1.01, 6),
        "breakoutLevel": round(resistance * 1.002, 6),
        "invalidation": round(max(support * 0.985, 0), 6),
        "tp1": round(resistance, 6),
        "tp2": round(resistance * 1.03, 6),
        "rr": 1.1,
        "atr": round(max(price * 0.015, 0.000001), 6),
        "emaFast": round(price, 6),
        "emaSlow": round(price, 6),
        "volumeRatio": 1.0,
        "history": [],
    }
