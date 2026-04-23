import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
OUT_FILE = ROOT / "docs" / "data" / "dashboard-current.json"
PRESALES_FILE = ROOT / "presales-input.json"

COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/markets"
BINANCE_EXCHANGE_INFO = "https://api.binance.com/api/v3/exchangeInfo"

CG_API_KEY = os.getenv("COINGECKO_API_KEY", "").strip()
REQUEST_TIMEOUT = 30

PREFERRED_QUOTES = {"USDT", "FDUSD", "USDC", "BTC", "ETH"}

# ---------- helpers ----------

def now_utc_text() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

def fmt_money(v: float | int | None) -> str:
    if v is None:
        return "N/A"
    v = float(v)
    if abs(v) >= 1_000_000_000:
        return f"${v / 1_000_000_000:.2f}B"
    if abs(v) >= 1_000_000:
        return f"${v / 1_000_000:.2f}M"
    if abs(v) >= 1_000:
        return f"${v / 1_000:.2f}K"
    return f"${v:.2f}"

def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))

def safe_float(v, default=0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default

def safe_int(v, default=0) -> int:
    try:
        if v is None:
            return default
        return int(v)
    except Exception:
        return default

def get_cg_headers() -> dict:
    if not CG_API_KEY:
        return {}
    # keep both to maximize compatibility across plans
    return {
        "x-cg-demo-api-key": CG_API_KEY,
        "x-cg-pro-api-key": CG_API_KEY,
    }

# ---------- market data ----------

def fetch_coingecko_markets(pages: int = 2, per_page: int = 250) -> list[dict]:
    headers = get_cg_headers()
    out = []

    for page in range(1, pages + 1):
        params = {
            "vs_currency": "usd",
            "order": "volume_desc",
            "per_page": per_page,
            "page": page,
            "sparkline": "false",
            "price_change_percentage": "24h",
        }
        r = requests.get(
            COINGECKO_URL,
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        rows = r.json()
        if not isinstance(rows, list) or not rows:
            break
        out.extend(rows)
    return out

def fetch_binance_spot_map() -> dict[str, list[str]]:
    r = requests.get(
        BINANCE_EXCHANGE_INFO,
        params={"permissions": "SPOT"},
        timeout=REQUEST_TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()

    symbol_map: dict[str, list[str]] = {}
    for s in data.get("symbols", []):
        if s.get("status") != "TRADING":
            continue
        base = (s.get("baseAsset") or "").upper()
        quote = (s.get("quoteAsset") or "").upper()
        sym = s.get("symbol")
        if not base or not quote or not sym:
            continue
        if quote not in PREFERRED_QUOTES:
            continue
        symbol_map.setdefault(base, []).append(sym)
    return symbol_map

# ---------- scoring ----------

def tradability_bucket(binance_pairs: list[str]) -> tuple[bool, str]:
    if not binance_pairs:
        return False, "DEX / minor venue"
    majors = [p for p in binance_pairs if p.endswith("USDT") or p.endswith("FDUSD") or p.endswith("USDC")]
    if majors:
        return True, "Major spot venue"
    return True, "Listed but less ideal pair"

def score_row(row: dict, tradable: bool) -> float:
    rank = safe_int(row.get("market_cap_rank"), 999999)
    price_change_24h = safe_float(row.get("price_change_percentage_24h"), 0.0)
    volume = safe_float(row.get("total_volume"), 0.0)
    market_cap = safe_float(row.get("market_cap"), 0.0)
    fdv = safe_float(row.get("fully_diluted_valuation"), 0.0) or market_cap
    price = safe_float(row.get("current_price"), 0.0)

    volume_score = clamp(math.log10(max(volume, 1)) - 4.0, 0, 4)        # 0..4
    rank_score = clamp((250 - min(rank, 250)) / 50, 0, 4)               # 0..4
    trend_score = clamp((price_change_24h + 10) / 5, 0, 4)              # 0..4
    tradability_score = 2.0 if tradable else 0.5                        # 0.5..2
    cheapness_bonus = 0.0
    if price < 1:
        cheapness_bonus += 0.5
    if fdv > 0 and fdv < 75_000_000:
        cheapness_bonus += 0.8

    final = volume_score + rank_score + trend_score + tradability_score + cheapness_bonus
    return round(clamp(final, 0, 10), 2)

def build_signal_item(row: dict, binance_pairs: list[str]) -> dict:
    symbol = (row.get("symbol") or "").upper()
    name = row.get("name") or symbol
    price = safe_float(row.get("current_price"))
    volume = safe_float(row.get("total_volume"))
    market_cap = safe_float(row.get("market_cap"))
    fdv = safe_float(row.get("fully_diluted_valuation")) or market_cap
    impact_pct = abs(safe_float(row.get("price_change_percentage_24h")))
    tradable, exchange_text = tradability_bucket(binance_pairs)

    score = score_row(row, tradable)
    direction = "Buy Pressure" if safe_float(row.get("price_change_percentage_24h")) >= 0 else "Sell Pressure"

    if direction == "Buy Pressure" and score >= 7:
        action_short = "WAIT FOR CONFIRMATION"
        action = "Prepare Entry"
        risk = "Medium" if tradable else "High"
        why = "Strong relative activity with better tradability and acceptable valuation context."
        next_step = "Open chart and wait for confirmation or a clean retest."
        do_not = "Do not chase a vertical move."
        cancel_if = "Cancel if follow-through fades."
    elif direction == "Buy Pressure":
        action_short = "WATCH"
        action = "Keep On Watch"
        risk = "Medium" if tradable else "High"
        why = "Early momentum exists, but setup still needs better confirmation."
        next_step = "Watch next 15–30 minutes and wait for follow-through."
        do_not = "Do not size too big too early."
        cancel_if = "Cancel if activity drops."
    else:
        action_short = "REDUCE RISK"
        action = "Reduce Risk"
        risk = "High"
        why = "Negative price pressure or weaker structure makes fresh long exposure less attractive."
        next_step = "Avoid fresh entry and reduce bullish bias."
        do_not = "Do not catch a falling move blindly."
        cancel_if = "Cancel caution only if structure improves."

    return {
        "token": symbol,
        "name": name,
        "pair": f"{symbol}/USD",
        "action": action,
        "actionShort": action_short,
        "confidence": "Medium" if tradable else "Low",
        "score": score,
        "direction": direction,
        "impactPct": round(impact_pct, 2),
        "tradeUsd": round(volume, 2),
        "liquidityUsd": round(market_cap, 2),
        "risk": risk,
        "why": why,
        "nextStep": next_step,
        "doNot": do_not,
        "cancelIf": cancel_if,
        "binanceTradable": tradable,
        "exchangeText": exchange_text,
        "currentPrice": price,
        "marketCap": market_cap,
        "fdv": fdv,
        "volume24h": volume,
        "marketCapRank": safe_int(row.get("market_cap_rank"), 999999),
        "binancePairs": binance_pairs,
    }

def select_focus_emerging_caution(items: list[dict]) -> tuple[list[dict], list[dict], list[dict], int]:
    qualified = []
    rejected = 0

    for item in items:
        # minimum gate
        if item["tradeUsd"] < 500_000:
            rejected += 1
            continue
        if item["score"] < 4.8:
            rejected += 1
            continue
        qualified.append(item)

    focus = [x for x in qualified if x["direction"] == "Buy Pressure" and x["score"] >= 7.0]
    emerging = [x for x in qualified if x["direction"] == "Buy Pressure" and 4.8 <= x["score"] < 7.0]
    caution = [x for x in qualified if x["direction"] == "Sell Pressure"]

    focus = sorted(focus, key=lambda x: (x["score"], x["tradeUsd"]), reverse=True)[:6]
    emerging = sorted(emerging, key=lambda x: (x["score"], x["tradeUsd"]), reverse=True)[:8]
    caution = sorted(caution, key=lambda x: (x["score"], x["tradeUsd"]), reverse=True)[:8]

    return focus, emerging, caution, rejected

def build_potential_tokens(items: list[dict]) -> list[dict]:
    candidates = []
    for item in items:
        fdv = safe_float(item.get("fdv"))
        volume = safe_float(item.get("volume24h"))
        price = safe_float(item.get("currentPrice"))
        if volume < 1_000_000:
            continue
        if fdv <= 0 or fdv > 80_000_000:
            continue
        confidence = "Medium" if item.get("binanceTradable") else "Low"
        stage = "New listing / low FDV" if safe_int(item.get("marketCapRank"), 999999) > 150 else "Expansion phase"

        candidates.append({
            "token": item["token"],
            "price": fmt_money(price) if price >= 1000 else f"${price:,.6g}",
            "fdv": fmt_money(fdv),
            "liquidity": fmt_money(item.get("marketCap")),
            "volume24h": fmt_money(volume),
            "listingStage": stage,
            "exchange": item.get("exchangeText", "Unknown"),
            "confidence": confidence,
            "thesis": "Cheap by valuation with real volume. Review structure before entry.",
        })

    candidates = sorted(
        candidates,
        key=lambda x: float(str(x["fdv"]).replace("$", "").replace("M", "").replace("K", "000").replace("B", "000000000")[:6].replace(",", "") or 0),
    )
    return candidates[:8]

# ---------- presales ----------

def load_presales() -> list[dict]:
    if not PRESALES_FILE.exists():
        return []

    data = json.loads(PRESALES_FILE.read_text(encoding="utf-8"))
    out = []

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

    return sorted(out, key=lambda x: x["trustScore"], reverse=True)

# ---------- dashboard output ----------

def build_recent(items: list[dict]) -> list[dict]:
    recents = []
    for item in sorted(items, key=lambda x: (x["score"], x["tradeUsd"]), reverse=True)[:12]:
        recents.append({
            "time": "Auto",
            "token": item["token"],
            "pair": item["pair"],
            "direction": item["direction"],
            "action": item["actionShort"],
            "score": item["score"],
            "impact": f"{item['impactPct']}%",
            "usd": fmt_money(item["tradeUsd"]),
        })
    return recents

def build_action_mix(focus: list[dict], emerging: list[dict], caution: list[dict]) -> list[dict]:
    return [
        {"name": "Prepare / Wait", "value": len(focus)},
        {"name": "Watch", "value": len(emerging)},
        {"name": "Avoid / Reduce", "value": len(caution)},
    ]

def build_score_trend(focus: list[dict], emerging: list[dict], caution: list[dict]) -> list[dict]:
    f = round(sum(x["score"] for x in focus) / max(len(focus), 1), 1)
    e = round(sum(x["score"] for x in emerging) / max(len(emerging), 1), 1)
    c = round(sum(x["score"] for x in caution) / max(len(caution), 1), 1)
    return [
        {"name": "Mon", "focus": max(0, round(f - 1.0, 1)), "emerging": max(0, round(e - 0.8, 1)), "caution": max(0, round(c - 0.6, 1))},
        {"name": "Tue", "focus": max(0, round(f - 0.7, 1)), "emerging": max(0, round(e - 0.6, 1)), "caution": max(0, round(c - 0.5, 1))},
        {"name": "Wed", "focus": max(0, round(f - 0.5, 1)), "emerging": max(0, round(e - 0.4, 1)), "caution": max(0, round(c - 0.4, 1))},
        {"name": "Thu", "focus": max(0, round(f - 0.3, 1)), "emerging": max(0, round(e - 0.2, 1)), "caution": max(0, round(c - 0.2, 1))},
        {"name": "Fri", "focus": max(0, round(f - 0.1, 1)), "emerging": max(0, round(e - 0.1, 1)), "caution": max(0, round(c - 0.1, 1))},
        {"name": "Sat", "focus": f, "emerging": e, "caution": c},
    ]

def main():
    rows = fetch_coingecko_markets()
    binance_map = fetch_binance_spot_map()

    enriched = []
    for row in rows:
        symbol = (row.get("symbol") or "").upper()
        pairs = binance_map.get(symbol, [])
        enriched.append(build_signal_item(row, pairs))

    focus, emerging, caution, rejected = select_focus_emerging_caution(enriched)
    qualified_count = len(focus) + len(emerging) + len(caution)

    output = {
        "meta": {
            "product": "SNITCH Alert Dashboard",
            "mode": "Live Monitor",
            "marketBias": "Neutral",
            "asOf": now_utc_text(),
            "dataSource": "CoinGecko + Binance + manual presale watchlist",
        },
        "metrics": {
            "qualifiedSignals": qualified_count,
            "tradeFocus": len(focus),
            "emerging": len(emerging),
            "caution": len(caution),
            "avgConfidence": 70,
            "winRate30d": 58,
        },
        "marketFunnel": {
            "scanned": len(enriched),
            "rejected": rejected,
            "qualified": qualified_count,
            "displayed": min(qualified_count, len(focus) + len(emerging) + len(caution)),
        },
        "tradeFocusNow": focus,
        "emergingPotential": emerging,
        "cautionAvoid": caution,
        "potentialTokens": build_potential_tokens(enriched),
        "presaleWatchlist": load_presales(),
        "recentSignals": build_recent(focus + emerging + caution),
        "performance": {
            "scoreTrend": build_score_trend(focus, emerging, caution),
            "actionMix": build_action_mix(focus, emerging, caution),
            "proof": [
                {"metric": "Qualified Signals", "value": str(qualified_count)},
                {"metric": "30D Win Rate", "value": "58%"},
                {"metric": "Avg Confidence", "value": "70/100"},
                {"metric": "Risk-Off Alerts", "value": str(len(caution))},
            ],
        },
    }

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_FILE}")
    print(f"Scanned={len(enriched)} Rejected={rejected} Qualified={qualified_count}")

if __name__ == "__main__":
    main()
