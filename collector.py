from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests

from signal_engine import MAJOR_SYMBOLS, build_action_plan
from snr_engine import (
    build_fallback_snr,
    build_snr_from_klines,
    choose_best_pair,
    fetch_binance_spot_map,
    fetch_klines,
)

ROOT = Path(__file__).resolve().parent
OUT_FILE = ROOT / "docs" / "data" / "dashboard-current.json"
RULES_FILE = ROOT / "dashboard_rules.json"
PRESALES_FILE = ROOT / "presales-input.json"
BLACKLIST_FILE = ROOT / "manual_blacklist.json"
WATCHLIST_FILE = ROOT / "manual_watchlist.json"

COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/markets"
CG_API_KEY = ""
REQUEST_TIMEOUT = 30

STABLE_SYMBOLS = {
    "USDT", "USDC", "BUSD", "FDUSD", "TUSD", "DAI", "USDE", "PYUSD", "RLUSD",
    "USD1", "USDQ", "USDR", "USDON", "USDL", "USDP", "GUSD", "FRAX", "SUSDS",
    "USDS", "EURC", "LUSD", "CRVUSD", "MIM", "USDD", "XAUT", "PAXG",
}
WRAPPED_SYMBOLS = {"WBTC", "WETH", "STETH", "WSTETH", "WEETH", "MSOL", "BNSOL", "CBBTC"}


def safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def safe_int(v: Any, default: int = 0) -> int:
    try:
        if v is None:
            return default
        return int(v)
    except Exception:
        return default


def now_utc_text() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def fmt_money(v: Any) -> str:
    try:
        val = float(v)
    except Exception:
        return "N/A"

    if abs(val) >= 1_000_000_000:
        return f"${val / 1_000_000_000:.2f}B"
    if abs(val) >= 1_000_000:
        return f"${val / 1_000_000:.2f}M"
    if abs(val) >= 1_000:
        return f"${val / 1_000:.2f}K"
    return f"${val:.2f}"


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_output(payload: Dict[str, Any]) -> None:
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def get_cg_headers() -> Dict[str, str]:
    if not CG_API_KEY:
        return {}
    return {
        "x-cg-demo-api-key": CG_API_KEY,
        "x-cg-pro-api-key": CG_API_KEY,
    }


def fetch_coingecko_markets(rules: Dict[str, Any]) -> List[Dict[str, Any]]:
    pages = int(rules.get("coingecko_pages", 2))
    per_page = int(rules.get("coingecko_per_page", 250))
    headers = get_cg_headers()

    out: List[Dict[str, Any]] = []
    for page in range(1, pages + 1):
        params = {
            "vs_currency": "usd",
            "order": "volume_desc",
            "per_page": per_page,
            "page": page,
            "sparkline": "false",
            "price_change_percentage": "24h",
        }
        r = requests.get(COINGECKO_URL, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        rows = r.json()
        if not isinstance(rows, list) or not rows:
            break
        out.extend(rows)
    return out


def is_stable_like(symbol: str, name: str) -> bool:
    sym = (symbol or "").upper()
    low = (name or "").lower()

    if sym in STABLE_SYMBOLS:
        return True
    if sym.startswith("USD") or sym.endswith("USD"):
        return True

    hints = ("stable", "dollar", "tether", "trueusd", "frax", "pax dollar", "usd ")
    return any(h in low for h in hints)


def is_wrapped_like(symbol: str, name: str, blacklist: Dict[str, Any]) -> bool:
    sym = (symbol or "").upper()
    low = (name or "").lower()

    if sym in WRAPPED_SYMBOLS:
        return True

    for phrase in blacklist.get("name_contains", []):
        if phrase.lower() in low:
            return True

    return False


def is_blacklisted(symbol: str, blacklist: Dict[str, Any]) -> bool:
    return (symbol or "").upper() in {x.upper() for x in blacklist.get("symbols", [])}


def low_quality_symbol(symbol: str, rules: Dict[str, Any]) -> bool:
    sym = (symbol or "").upper()
    min_len = int(rules.get("min_quality_symbol_len", 2))
    max_len = int(rules.get("max_quality_symbol_len", 12))

    if len(sym) < min_len or len(sym) > max_len:
        return True
    if not sym.isalnum():
        return True
    if sym.isdigit():
        return True
    if len(sym) == 1:
        return True
    return False


def tradability_bucket(binance_pairs: List[str]) -> Tuple[bool, str]:
    if not binance_pairs:
        return False, "Unknown / not verified on Binance"

    preferred = [p for p in binance_pairs if p.endswith(("USDT", "FDUSD", "USDC"))]
    if preferred:
        return True, "Major spot venue"
    return True, "Listed but less ideal pair"


def is_major_symbol(symbol: str, row: Dict[str, Any]) -> bool:
    sym = (symbol or "").upper()
    rank = safe_int(row.get("market_cap_rank"), 999999)
    market_cap = safe_float(row.get("market_cap"))

    if sym in MAJOR_SYMBOLS:
        return True
    if rank <= 25:
        return True
    if market_cap >= 1_200_000_000:
        return True
    return False


def prefilter_reason(
    row: Dict[str, Any],
    blacklist: Dict[str, Any],
    rules: Dict[str, Any],
) -> str | None:
    symbol = (row.get("symbol") or "").upper()
    name = row.get("name") or symbol
    volume = safe_float(row.get("total_volume"))
    market_cap = safe_float(row.get("market_cap"))
    fdv = safe_float(row.get("fully_diluted_valuation")) or market_cap
    rank = safe_int(row.get("market_cap_rank"), 999999)
    price_change = abs(safe_float(row.get("price_change_percentage_24h"), 0.0))

    if is_blacklisted(symbol, blacklist):
        return "manual_blacklist"
    if low_quality_symbol(symbol, rules):
        return "manual_blacklist"
    if is_stable_like(symbol, name):
        return "stablecoin"
    if is_wrapped_like(symbol, name, blacklist):
        return "wrapped_or_derivative"
    if volume < safe_float(rules.get("min_scan_volume_usd", 400000)):
        return "too_illiquid"

    if rank <= 5 and market_cap > 10_000_000_000 and price_change < 0.35:
        return "major_not_actionable"

    if fdv > safe_float(rules.get("hard_reject_fdv_usd", 9_000_000_000)) and rank > 80 and price_change < 0.8:
        return "too_large_for_sniper"

    return None


def weak_momentum_reason(item: Dict[str, Any], rules: Dict[str, Any]) -> str | None:
    if item.get("isMajor"):
        return None

    score = safe_float(item.get("score"))
    impact = safe_float(item.get("impactPct"))
    trade_usd = safe_float(item.get("tradeUsd"))
    direction = item.get("direction", "")

    if direction == "Sell Pressure" and score < safe_float(rules.get("min_caution_keep_score", 5.0)):
        return "weak_momentum"

    if direction == "Buy Pressure":
        if score < safe_float(rules.get("min_emerging_score", 5.0)):
            return "weak_momentum"
        if impact < safe_float(rules.get("min_keep_impact_pct", 0.35)) and trade_usd < safe_float(rules.get("min_keep_trade_usd", 1_500_000)):
            return "weak_momentum"

    return None


def calc_rr_quality(item: Dict[str, Any]) -> float:
    rr = safe_float(item.get("rr"))
    if rr <= 0:
        return 0.0
    if rr >= 2.4:
        return 1.0
    if rr >= 2.0:
        return 0.9
    if rr >= 1.7:
        return 0.78
    if rr >= 1.5:
        return 0.68
    if rr >= 1.3:
        return 0.55
    if rr >= 1.15:
        return 0.40
    return 0.20


def calc_execution_rank(item: Dict[str, Any]) -> float:
    score = safe_float(item.get("score"))
    impact = safe_float(item.get("impactPct"))
    rrq = calc_rr_quality(item)
    trade_usd = safe_float(item.get("tradeUsd"))
    trade_bonus = 0.0

    if trade_usd >= 100_000_000:
        trade_bonus = 1.0
    elif trade_usd >= 30_000_000:
        trade_bonus = 0.8
    elif trade_usd >= 10_000_000:
        trade_bonus = 0.6
    elif trade_usd >= 3_000_000:
        trade_bonus = 0.4

    setup_bonus = 0.0
    if item.get("actionShort") == "BUY NOW":
        setup_bonus = 1.2
    elif item.get("actionShort") == "BUY ON RETEST":
        setup_bonus = 0.9
    elif item.get("actionShort") == "WAIT BREAKOUT":
        setup_bonus = 0.7
    elif item.get("actionShort") == "WAIT FOR CONFIRMATION":
        setup_bonus = 0.5

    return round((score * 0.60) + (impact * 0.16) + (rrq * 10 * 0.14) + trade_bonus + setup_bonus, 4)


def calc_sniper_rank(item: Dict[str, Any]) -> float:
    score = safe_float(item.get("score"))
    impact = safe_float(item.get("impactPct"))
    market_cap = safe_float(item.get("marketCap"))
    fdv = safe_float(item.get("fdv"))
    rrq = calc_rr_quality(item)

    cheap_bonus = 0.0
    if 0 < fdv <= 20_000_000:
        cheap_bonus = 1.8
    elif fdv <= 50_000_000:
        cheap_bonus = 1.45
    elif fdv <= 100_000_000:
        cheap_bonus = 1.0
    elif fdv <= 180_000_000:
        cheap_bonus = 0.65

    if 0 < market_cap <= 20_000_000:
        cheap_bonus += 0.8
    elif market_cap <= 60_000_000:
        cheap_bonus += 0.5

    setup_bonus = 0.0
    if item.get("actionShort") == "BUY NOW":
        setup_bonus = 1.0
    elif item.get("actionShort") == "BUY ON RETEST":
        setup_bonus = 0.8
    elif item.get("actionShort") == "WAIT BREAKOUT":
        setup_bonus = 0.6
    elif item.get("actionShort") == "WAIT FOR CONFIRMATION":
        setup_bonus = 0.4

    return round((score * 0.46) + (impact * 0.22) + (rrq * 10 * 0.18) + cheap_bonus + setup_bonus, 4)


def calc_opportunity_rank(item: Dict[str, Any]) -> float:
    opp = safe_float(item.get("opportunityScore"))
    score = safe_float(item.get("score"))
    impact = safe_float(item.get("impactPct"))
    return round((opp * 0.55) + (score * 0.25) + (impact * 0.20), 4)


def build_potential_token(item: Dict[str, Any]) -> Dict[str, Any]:
    price = safe_float(item.get("currentPrice"))
    return {
        "token": item["token"],
        "price": f"${price:,.6g}" if price < 1000 else fmt_money(price),
        "fdv": fmt_money(item.get("fdv")),
        "liquidity": fmt_money(item.get("marketCap")),
        "volume24h": fmt_money(item.get("volume24h")),
        "listingStage": "New listing / low FDV" if safe_int(item.get("marketCapRank"), 999999) > 120 else "Expansion phase",
        "exchange": item.get("exchangeText", "Unknown"),
        "confidence": item.get("confidence", "Low"),
        "thesis": item.get("whyCheap", "Cheap by valuation with real volume. Review structure before entry."),
        "sector": item.get("sector", "General"),
        "entryType": item.get("entryType", "Watchlist"),
        "buyZone": item.get("buyZone", []),
        "breakoutTrigger": item.get("breakoutTrigger"),
        "invalidation": item.get("invalidation"),
        "tp1": item.get("tp1"),
        "tp2": item.get("tp2"),
        "rr": item.get("rr"),
    }


def build_recent(items: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    out = []
    for item in items[:limit]:
        out.append(
            {
                "time": "Auto",
                "token": item["token"],
                "pair": item["pair"],
                "direction": item["direction"],
                "action": item["actionShort"],
                "score": item["score"],
                "impact": f"{item['impactPct']}%",
                "usd": fmt_money(item["tradeUsd"]),
            }
        )
    return out


def build_action_mix(focus: List[Dict[str, Any]], emerging: List[Dict[str, Any]], caution: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {"name": "Prepare / Wait", "
