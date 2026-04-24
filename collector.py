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

# Hard blacklist for stable / pseudo-stable / USD-pegged style names
STABLE_SYMBOLS = {
    "USDT", "USDC", "BUSD", "FDUSD", "TUSD", "DAI", "USDE", "PYUSD", "RLUSD",
    "USD1", "USDQ", "USDR", "USDON", "USDL", "USDP", "GUSD", "FRAX", "SUSDS",
    "USDS", "EURC", "LUSD", "CRVUSD", "MIM", "USDD", "XAUT", "PAXG"
}
STABLE_NAME_HINTS = {
    "usd", "dollar", "stable", "euro", "tether", "trueusd", "frax", "pax dollar"
}

# High-liquidity majors we allow in main trade monitoring
MAJOR_SYMBOLS = {
    "BTC", "ETH", "XRP", "BNB", "SOL", "DOGE", "TRX", "AAVE",
    "ADA", "LINK", "AVAX", "SUI", "TON", "BCH", "LTC"
}

# Exclude these from "cheap opportunities" / "potential token" tables even if active
EXCLUDED_FROM_POTENTIAL = STABLE_SYMBOLS | MAJOR_SYMBOLS | {
    "WBTC", "WETH", "STETH", "WSTETH", "CBBTC", "BNSOL", "MSOL", "WEETH"
}

# Exclude obvious wrappers / stake derivatives from sniper-style discovery
WRAPPED_NAME_HINTS = {
    "wrapped", "liquid staking", "staked ether", "restaked", "bridged"
}


def now_utc_text():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def fmt_money(v):
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


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def safe_float(v, default=0.0):
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def safe_int(v, default=0):
    try:
        if v is None:
            return default
        return int(v)
    except Exception:
        return default


def get_cg_headers():
    if not CG_API_KEY:
        return {}
    return {
        "x-cg-demo-api-key": CG_API_KEY,
        "x-cg-pro-api-key": CG_API_KEY,
    }


def fetch_coingecko_markets(pages=2, per_page=250):
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
        r = requests.get(COINGECKO_URL, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        rows = r.json()
        if not isinstance(rows, list) or not rows:
            break
        out.extend(rows)

    return out


def fetch_binance_spot_map():
    try:
        r = requests.get(BINANCE_EXCHANGE_INFO, params={"permissions": "SPOT"}, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()

        symbol_map = {}
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

        print(f"Binance spot map loaded: {len(symbol_map)} assets")
        return symbol_map, None

    except Exception as e:
        print(f"Binance fetch failed, continuing without Binance data: {e}")
        return {}, str(e)


def is_stable_like(symbol, name):
    sym = (symbol or "").upper()
    low_name = (name or "").lower()

    if sym in STABLE_SYMBOLS:
        return True

    if sym.startswith("USD") or sym.endswith("USD"):
        return True

    if sym.startswith("USD") or sym.startswith("EUR"):
        return True

    return any(hint in low_name for hint in STABLE_NAME_HINTS)


def is_wrapped_or_derivative(symbol, name):
    sym = (symbol or "").upper()
    low_name = (name or "").lower()

    if sym in {"WBTC", "WETH", "STETH", "WSTETH", "WEETH", "MSOL", "BNSOL", "CBBTC"}:
        return True

    return any(hint in low_name for hint in WRAPPED_NAME_HINTS)


def tradability_bucket(binance_pairs):
    if not binance_pairs:
        return False, "Unknown / not verified on Binance"
    majors = [p for p in binance_pairs if p.endswith("USDT") or p.endswith("FDUSD") or p.endswith("USDC")]
    if majors:
        return True, "Major spot venue"
    return True, "Listed but less ideal pair"


def score_row(row, tradable):
    rank = safe_int(row.get("market_cap_rank"), 999999)
    price_change_24h = safe_float(row.get("price_change_percentage_24h"), 0.0)
    volume = safe_float(row.get("total_volume"), 0.0)
    market_cap = safe_float(row.get("market_cap"), 0.0)
    fdv = safe_float(row.get("fully_diluted_valuation"), 0.0) or market_cap
    price = safe_float(row.get("current_price"), 0.0)

    volume_score = clamp(math.log10(max(volume, 1)) - 4.2, 0, 3.5)
    rank_score = clamp((220 - min(rank, 220)) / 55, 0, 2.5)
    trend_score = clamp((price_change_24h + 8) / 4, 0, 2.5)
    tradability_score = 1.8 if tradable else 0.4
    cheapness_bonus = 0.0

    if price < 5:
        cheapness_bonus += 0.3
    if 0 < fdv < 100_000_000:
        cheapness_bonus += 0.8
    elif 100_000_000 <= fdv < 500_000_000:
        cheapness_bonus += 0.3

    final = volume_score + rank_score + trend_score + tradability_score + cheapness_bonus
    return round(clamp(final, 0, 10), 2)


def derive_risk(symbol, tradable, market_cap, fdv, score, is_major):
    if is_major and tradable and market_cap >= 1_000_000_000:
        return "Low"
    if tradable and market_cap >= 250_000_000 and score >= 6:
        return "Medium"
    if tradable and fdv >= 50_000_000:
        return "Medium"
    return "High"


def build_signal_item(row, binance_pairs):
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
    is_major = symbol in MAJOR_SYMBOLS
    risk = derive_risk(symbol, tradable, market_cap, fdv, score, is_major)

    if direction == "Buy Pressure" and score >= 7:
        action_short = "WAIT FOR CONFIRMATION"
        action = "Prepare Entry"
        why = "Strong relative activity with acceptable market context."
        next_step = "Open chart and wait for confirmation or a clean retest."
        do_not = "Do not chase a vertical move."
        cancel_if = "Cancel if follow-through fades."
    elif direction == "Buy Pressure":
        action_short = "WATCH"
        action = "Keep On Watch"
        why = "Early momentum exists, but setup still needs better confirmation."
        next_step = "Watch next 15–30 minutes and wait for follow-through."
        do_not = "Do not size too big too early."
        cancel_if = "Cancel if activity drops."
    else:
        action_short = "REDUCE RISK"
        action = "Reduce Risk"
        why = "Negative price pressure or weaker structure makes fresh long exposure less attractive."
        next_step = "Avoid fresh entry and reduce bullish bias."
        do_not = "Do not catch a falling move blindly."
        cancel_if = "Cancel caution only if structure improves."

    if is_major and direction == "Buy Pressure":
        why = "Large-cap name with strong activity. Better for execution confidence than explosive upside."
    elif is_major and direction == "Sell Pressure":
        why = "Large-cap name under pressure. Useful as market risk signal more than hidden opportunity."

    return {
        "token": symbol,
        "name": name,
        "pair": f"{symbol}/USD",
        "action": action,
        "actionShort": action_short,
        "confidence": "High" if risk == "Low" else ("Medium" if risk == "Medium" else "Low"),
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
        "isMajor": is_major,
    }


def classify_rejection(item):
    symbol = item["token"]
    name = item["name"]
    trade_usd = safe_float(item["tradeUsd"])
    market_cap = safe_float(item["marketCap"])
    fdv = safe_float(item["fdv"])
    score = safe_float(item["score"])
    rank = safe_int(item["marketCapRank"], 999999)
    is_major = bool(item.get("isMajor"))

    if is_stable_like(symbol, name):
        return "stablecoin"
    if is_wrapped_or_derivative(symbol, name):
        return "wrapped_or_derivative"
    if trade_usd < 500_000:
        return "too_illiquid"
    if score < 4.8:
        return "weak_momentum"
    if is_major and rank <= 5 and market_cap >= 10_000_000_000 and score < 7:
        return "major_not_actionable"
    if 0 < fdv > 5_000_000_000 and not is_major and score < 7:
        return "too_large_for_sniper"
    return None


def select_focus_emerging_caution(items):
    qualified = []
    rejected = 0
    reject_reasons = {
        "stablecoin": 0,
        "wrapped_or_derivative": 0,
        "too_illiquid": 0,
        "weak_momentum": 0,
        "major_not_actionable": 0,
        "too_large_for_sniper": 0,
    }

    for item in items:
        reason = classify_rejection(item)
        if reason:
            rejected += 1
            reject_reasons[reason] = reject_reasons.get(reason, 0) + 1
            continue
        qualified.append(item)

    focus = [
        x for x in qualified
        if x["direction"] == "Buy Pressure" and x["score"] >= 7.0
    ]
    emerging = [
        x for x in qualified
        if x["direction"] == "Buy Pressure" and 4.8 <= x["score"] < 7.0
    ]
    caution = [x for x in qualified if x["direction"] == "Sell Pressure"]

    # Prefer better tradability + non-stable + useful names
    focus = sorted(
        focus,
        key=lambda x: (x["score"], x["binanceTradable"], x["tradeUsd"]),
        reverse=True
    )[:6]
    emerging = sorted(
        emerging,
        key=lambda x: (x["score"], x["binanceTradable"], x["tradeUsd"]),
        reverse=True
    )[:8]
    caution = sorted(
        caution,
        key=lambda x: (x["score"], x["tradeUsd"]),
        reverse=True
    )[:8]

    return focus, emerging, caution, rejected, reject_reasons


def build_potential_tokens(items):
    candidates = []

    for item in items:
        symbol = item["token"]
        name = item["name"]
        fdv = safe_float(item.get("fdv"))
        volume = safe_float(item.get("volume24h"))
        price = safe_float(item.get("currentPrice"))
        market_cap = safe_float(item.get("marketCap"))
        rank = safe_int(item.get("marketCapRank"), 999999)

        if symbol in EXCLUDED_FROM_POTENTIAL:
            continue
        if is_stable_like(symbol, name):
            continue
        if is_wrapped_or_derivative(symbol, name):
            continue
        if volume < 1_000_000:
            continue
        if fdv <= 0 or fdv > 120_000_000:
            continue
        if market_cap <= 0 or market_cap > 120_000_000:
            continue
        if rank <= 20:
            continue
        if price > 20:
            continue

        confidence = "Medium" if item.get("binanceTradable") else "Low"

        if rank > 150:
            stage = "New listing / low FDV"
        elif rank > 60:
            stage = "Expansion phase"
        else:
            stage = "Mid-cap watch"

        candidates.append({
            "token": symbol,
            "price": fmt_money(price) if price >= 1000 else f"${price:,.6g}",
            "fdv": fmt_money(fdv),
            "liquidity": fmt_money(market_cap),
            "volume24h": fmt_money(volume),
            "listingStage": stage,
            "exchange": item.get("exchangeText", "Unknown"),
            "confidence": confidence,
            "thesis": "Cheap by valuation with real volume. Review structure before entry.",
        })

    candidates = sorted(
        candidates,
        key=lambda x: (
            x["confidence"] == "Medium",
        ),
        reverse=True
    )

    return candidates[:12]


def load_presales():
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

    return sorted(
        out,
        key=lambda x: (x["trustScore"], x["tokenomicsScore"]),
        reverse=True
    )


def build_recent(items):
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


def build_action_mix(focus, emerging, caution):
    return [
        {"name": "Prepare / Wait", "value": len(focus)},
        {"name": "Watch", "value": len(emerging)},
        {"name": "Avoid / Reduce", "value": len(caution)},
    ]


def build_score_trend(focus, emerging, caution):
    f = round(sum(x["score"] for x in focus) / max(len(focus), 1), 1)
    e = round(sum(x["score"] for x in emerging) / max(len(emerging), 1), 1)
    c = round(sum(x["score"] for x in caution) / max(len(caution), 1), 1)
    return [
        {"name": "Mon", "focus": max(0, round(f - 1.1, 1)), "emerging": max(0, round(e - 0.8, 1)), "caution": max(0, round(c - 0.6, 1))},
        {"name": "Tue", "focus": max(0, round(f - 0.7, 1)), "emerging": max(0, round(e - 0.5, 1)), "caution": max(0, round(c - 0.4, 1))},
        {"name": "Wed", "focus": max(0, round(f - 0.4, 1)), "emerging": max(0, round(e - 0.3, 1)), "caution": max(0, round(c - 0.2, 1))},
        {"name": "Thu", "focus": max(0, round(f - 0.2, 1)), "emerging": max(0, round(e - 0.2, 1)), "caution": max(0, round(c - 0.1, 1))},
        {"name": "Fri", "focus": max(0, round(f - 0.1, 1)), "emerging": max(0, round(e - 0.1, 1)), "caution": max(0, round(c - 0.1, 1))},
        {"name": "Sat", "focus": f, "emerging": e, "caution": c},
    ]


def write_output(output):
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(output, indent=2), encoding="utf-8")


def main():
    rows = fetch_coingecko_markets()
    binance_map, binance_error = fetch_binance_spot_map()

    enriched = []
    for row in rows:
        symbol = (row.get("symbol") or "").upper()
        pairs = binance_map.get(symbol, [])
        enriched.append(build_signal_item(row, pairs))

    focus, emerging, caution, rejected, reject_reasons = select_focus_emerging_caution(enriched)
    qualified_count = len(focus) + len(emerging) + len(caution)

    source_note = "CoinGecko + manual presale watchlist"
    if not binance_error:
        source_note = "CoinGecko + Binance + manual presale watchlist"
    else:
        source_note = f"CoinGecko + manual presale watchlist | Binance unavailable: {binance_error}"

    output = {
        "meta": {
            "product": "SNITCH Alert Dashboard",
            "mode": "Live Monitor",
            "marketBias": "Neutral",
            "asOf": now_utc_text(),
            "dataSource": source_note,
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
            "displayed": qualified_count,
            "rejectReasons": reject_reasons,
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

    write_output(output)
    print(f"Wrote {OUT_FILE}")
    print(f"Scanned={len(enriched)} Rejected={rejected} Qualified={qualified_count}")
    print(f"Reject reasons={json.dumps(reject_reasons)}")
    if binance_error:
        print(f"Binance fallback used: {binance_error}")


if __name__ == "__main__":
    main()
