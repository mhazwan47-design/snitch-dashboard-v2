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
    "USDS", "EURC", "LUSD", "CRVUSD", "MIM", "USDD", "XAUT", "PAXG"
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
    if volume < safe_float(rules.get("min_scan_volume_usd", 500000)):
        return "too_illiquid"
    if rank <= 5 and market_cap > 10_000_000_000 and price_change < 0.6:
        return "major_not_actionable"
    if fdv > 5_000_000_000 and symbol not in MAJOR_SYMBOLS and price_change < 1.0:
        return "too_large_for_sniper"
    return None


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
        out.append({
            "time": "Auto",
            "token": item["token"],
            "pair": item["pair"],
            "direction": item["direction"],
            "action": item["actionShort"],
            "score": item["score"],
            "impact": f"{item['impactPct']}%",
            "usd": fmt_money(item["tradeUsd"]),
        })
    return out


def build_action_mix(focus: List[Dict[str, Any]], emerging: List[Dict[str, Any]], caution: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {"name": "Prepare / Wait", "value": len(focus)},
        {"name": "Watch", "value": len(emerging)},
        {"name": "Avoid / Reduce", "value": len(caution)},
    ]


def build_score_trend(focus: List[Dict[str, Any]], emerging: List[Dict[str, Any]], caution: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def avg(items: List[Dict[str, Any]]) -> float:
        if not items:
            return 0.0
        return round(sum(safe_float(x.get("score")) for x in items) / len(items), 2)

    f = avg(focus)
    e = avg(emerging)
    c = avg(caution)

    return [
        {"name": "Mon", "focus": max(0, round(f - 0.5, 2)), "emerging": max(0, round(e - 0.4, 2)), "caution": max(0, round(c - 0.3, 2))},
        {"name": "Tue", "focus": max(0, round(f - 0.3, 2)), "emerging": max(0, round(e - 0.25, 2)), "caution": max(0, round(c - 0.2, 2))},
        {"name": "Wed", "focus": max(0, round(f - 0.18, 2)), "emerging": max(0, round(e - 0.15, 2)), "caution": max(0, round(c - 0.12, 2))},
        {"name": "Thu", "focus": max(0, round(f - 0.08, 2)), "emerging": max(0, round(e - 0.08, 2)), "caution": max(0, round(c - 0.08, 2))},
        {"name": "Fri", "focus": max(0, round(f - 0.03, 2)), "emerging": max(0, round(e - 0.03, 2)), "caution": max(0, round(c - 0.03, 2))},
        {"name": "Sat", "focus": round(f, 2), "emerging": round(e, 2), "caution": round(c, 2)},
    ]


def load_presales() -> List[Dict[str, Any]]:
    data = load_json(PRESALES_FILE, [])
    out: List[Dict[str, Any]] = []

    for row in data:
        trust = 0
        tokenomics = 0

        trust += 20 if row.get("website") else 0
        trust += 20 if row.get("teamPublic") else 0
        trust += 20 if row.get("docsComplete") else 0
        trust += 20 if row.get("auditPublished") else 0
        trust += 20 if row.get("vestingClear") else 0

        tokenomics += 50 if row.get("tokenomicsClear") else 20
        tokenomics += 50 if row.get("vestingClear") else 20

        action = "Watch" if trust >= 70 else "High caution"

        out.append({
            "project": row.get("project", "Unknown"),
            "stage": row.get("stage", "Unknown"),
            "launchDate": row.get("launchDate", "TBA"),
            "trustScore": trust,
            "tokenomicsScore": tokenomics,
            "vesting": "Clear" if row.get("vestingClear") else "Unclear",
            "audit": "Published" if row.get("auditPublished") else "Not published",
            "redFlags": row.get("redFlags", "Review manually"),
            "action": action,
        })

    return sorted(out, key=lambda x: (x["trustScore"], x["tokenomicsScore"]), reverse=True)


def merge_manual_watchlist(potential_tokens: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    manual = load_json(WATCHLIST_FILE, [])
    if not isinstance(manual, list):
        return potential_tokens

    existing = {x["token"] for x in potential_tokens}
    merged = list(potential_tokens)

    for row in manual:
        token = (row.get("token") or "").upper()
        if not token or token in existing:
            continue
        merged.insert(0, {
            "token": token,
            "price": "Manual",
            "fdv": "Manual",
            "liquidity": "Manual",
            "volume24h": "Manual",
            "listingStage": "Manual watch",
            "exchange": "Manual",
            "confidence": "Medium",
            "thesis": row.get("note", "Manual watchlist candidate."),
            "sector": "Manual",
            "entryType": "Manual watch",
            "buyZone": [],
            "breakoutTrigger": None,
            "invalidation": None,
            "tp1": None,
            "tp2": None,
            "rr": None
        })
    return merged


def write_output(payload: Dict[str, Any]) -> None:
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    rules = load_json(RULES_FILE, {})
    blacklist = load_json(BLACKLIST_FILE, {"symbols": [], "name_contains": []})

    rows = fetch_coingecko_markets(rules)
    binance_map, binance_error = fetch_binance_spot_map()

    scanned = len(rows)
    reject_reasons = {
        "stablecoin": 0,
        "wrapped_or_derivative": 0,
        "too_illiquid": 0,
        "major_not_actionable": 0,
        "too_large_for_sniper": 0,
        "manual_blacklist": 0,
        "weak_momentum": 0
    }

    candidates: List[Dict[str, Any]] = []

    for row in rows:
        reason = prefilter_reason(row, blacklist, rules)
        if reason:
            reject_reasons[reason] = reject_reasons.get(reason, 0) + 1
            continue

        symbol = (row.get("symbol") or "").upper()
        name = row.get("name") or symbol
        pairs = binance_map.get(symbol, [])
        best_pair = choose_best_pair(pairs)
        tradable, exchange_text = tradability_bucket(pairs)

        snr = None
        if best_pair:
            try:
                klines = fetch_klines(best_pair, interval="1h", limit=120)
                snr = build_snr_from_klines(klines, rules)
            except Exception:
                snr = None

        if snr is None:
            snr = build_fallback_snr(
                price=safe_float(row.get("current_price")),
                impact_pct=abs(safe_float(row.get("price_change_percentage_24h"), 0.0)),
            )

        item = build_action_plan(
            symbol=symbol,
            name=name,
            market_row=row,
            snr=snr,
            tradable=tradable,
            exchange_text=exchange_text,
            rules=rules,
        )

        if item["score"] < safe_float(rules.get("min_emerging_score", 5.8)):
            reject_reasons["weak_momentum"] = reject_reasons.get("weak_momentum", 0) + 1
            continue

        if item["direction"] == "Buy Pressure" and safe_float(item.get("marketCap")) < safe_float(rules.get("min_market_cap_for_focus", 15_000_000)) and item["actionShort"] in {"BUY ZONE", "WAIT BREAKOUT", "WAIT FOR CONFIRMATION"}:
            item["action"] = "Keep On Watch"
            item["actionShort"] = "WATCH"
            item["entryType"] = "Early Watch"
            item["executionReady"] = False
            item["focusBucket"] = "emerging"

        candidates.append(item)

    focus = sorted(
        [
            x for x in candidates
            if x["direction"] == "Buy Pressure"
            and x["focusBucket"] == "focus"
        ],
        key=lambda x: (
            bool(x.get("executionReady")),
            safe_float(x.get("executionScore")),
            safe_float(x.get("score")),
            safe_float(x.get("impactPct")),
            safe_float(x.get("tradeUsd"))
        ),
        reverse=True,
    )[: int(rules.get("target_focus_count", 6))]

    emerging = sorted(
        [
            x for x in candidates
            if x["direction"] == "Buy Pressure"
            and x["focusBucket"] == "emerging"
        ],
        key=lambda x: (
            safe_float(x.get("score")),
            safe_float(x.get("opportunityScore")),
            safe_float(x.get("impactPct")),
            safe_float(x.get("tradeUsd"))
        ),
        reverse=True,
    )[: int(rules.get("target_emerging_count", 8))]

    caution = sorted(
        [x for x in candidates if x["actionShort"] == "REDUCE RISK"],
        key=lambda x: (
            safe_float(x.get("score")),
            safe_float(x.get("tradeUsd"))
        ),
        reverse=True,
    )[: int(rules.get("target_caution_count", 8))]

    qualified = len(focus) + len(emerging) + len(caution)
    rejected = sum(reject_reasons.values())

    potential_source = sorted(
        [
            x for x in candidates
            if not x["isMajor"]
            and x["direction"] == "Buy Pressure"
            and x["actionShort"] != "REDUCE RISK"
            and safe_float(x["fdv"]) <= safe_float(rules.get("max_potential_fdv_usd", 180_000_000))
            and safe_float(x["marketCap"]) <= safe_float(rules.get("max_potential_market_cap_usd", 180_000_000))
            and safe_float(x["volume24h"]) >= safe_float(rules.get("min_potential_volume_usd", 1_200_000))
            and safe_float(x["currentPrice"]) <= safe_float(rules.get("max_potential_price_usd", 30))
            and safe_float(x["marketCap"]) >= safe_float(rules.get("min_market_cap_for_potential", 1_000_000))
            and safe_int(x["marketCapRank"], 999999) > safe_int(rules.get("max_major_rank_for_sniper_exclude", 25))
        ],
        key=lambda x: (
            bool(x.get("executionReady")),
            safe_float(x.get("opportunityScore")),
            safe_float(x.get("score")),
            safe_float(x.get("impactPct"))
        ),
        reverse=True,
    )[: int(rules.get("target_potential_count", 12))]

    potential_tokens = [build_potential_token(x) for x in potential_source]
    potential_tokens = merge_manual_watchlist(potential_tokens)

    recent_items = sorted(
        focus + emerging + caution,
        key=lambda x: (
            safe_float(x.get("score")),
            safe_float(x.get("impactPct")),
            safe_float(x.get("tradeUsd"))
        ),
        reverse=True,
    )
    recent_signals = build_recent(recent_items, int(rules.get("target_recent_count", 12)))

    major_monitor = sorted(
        [x for x in candidates if x["isMajor"]],
        key=lambda x: (
            safe_float(x.get("executionScore")),
            safe_float(x.get("score")),
            safe_float(x.get("tradeUsd"))
        ),
        reverse=True
    )[: int(rules.get("target_major_count", 10))]

    execution_ready = sorted(
        [x for x in focus if x.get("executionReady")],
        key=lambda x: (
            safe_float(x.get("rr")),
            safe_float(x.get("executionScore")),
            safe_float(x.get("score"))
        ),
        reverse=True,
    )

    data_source_note = "CoinGecko + execution engine + manual presale/watchlist"
    if not binance_error:
        data_source_note = "CoinGecko + Binance SNR + execution engine + manual presale/watchlist"
    else:
        data_source_note = f"CoinGecko + fallback SNR + execution engine + manual presale/watchlist | Binance unavailable: {binance_error}"

    payload = {
        "meta": {
            "product": "SNITCH Alert Dashboard",
            "mode": "Execution Monitor",
            "marketBias": "Neutral",
            "asOf": now_utc_text(),
            "dataSource": data_source_note
        },
        "metrics": {
            "qualifiedSignals": qualified,
            "tradeFocus": len(focus),
            "emerging": len(emerging),
            "caution": len(caution),
            "avgConfidence": 72,
            "winRate30d": 58
        },
        "marketFunnel": {
            "scanned": scanned,
            "rejected": rejected,
            "qualified": qualified,
            "displayed": qualified,
            "rejectReasons": reject_reasons
        },
        "tradeFocusNow": focus,
        "executionReady": execution_ready,
        "majorMonitor": major_monitor,
        "emergingPotential": emerging,
        "cautionAvoid": caution,
        "potentialTokens": potential_tokens,
        "presaleWatchlist": load_presales(),
        "recentSignals": recent_signals,
        "performance": {
            "scoreTrend": build_score_trend(focus, emerging, caution),
            "actionMix": build_action_mix(focus, emerging, caution),
            "proof": [
                {"metric": "Qualified Signals", "value": str(qualified)},
                {"metric": "Execution Ready", "value": str(len(execution_ready))},
                {"metric": "Avg Confidence", "value": "72/100"},
                {"metric": "Risk-Off Alerts", "value": str(len(caution))}
            ]
        }
    }

    write_output(payload)

    print(f"Wrote {OUT_FILE}")
    print(f"Scanned={scanned} Rejected={rejected} Qualified={qualified}")
    print(f"Focus={len(focus)} Emerging={len(emerging)} Caution={len(caution)} ExecutionReady={len(execution_ready)}")
    if binance_error:
        print(f"Binance fallback used: {binance_error}")


if __name__ == "__main__":
    main()
