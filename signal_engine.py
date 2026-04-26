from __future__ import annotations

from typing import Any, Dict, Tuple


MAJOR_SYMBOLS = {
    "BTC", "ETH", "XRP", "BNB", "SOL", "DOGE", "TRX", "AAVE",
    "ADA", "LINK", "AVAX", "SUI", "TON", "BCH", "LTC"
}

SECTOR_MAP = {
    "ARB": "L2",
    "OP": "L2",
    "ATOM": "Interoperability",
    "ONDO": "RWA",
    "TRUMP": "Meme",
    "DOGE": "Meme",
    "SHIB": "Meme",
    "RENDER": "AI / Infra",
    "FET": "AI",
    "FIL": "Storage",
    "AAVE": "DeFi",
    "UNI": "DeFi",
    "ONDO": "RWA",
    "LINK": "Oracle",
    "ICP": "Infra",
    "TON": "Infra",
    "APT": "L1",
    "SUI": "L1",
    "ALGO": "L1",
    "ATOM": "Infra",
}


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


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


def fmt_price(v: float) -> str:
    if v >= 1000:
        return f"{v:,.2f}"
    if v >= 1:
        return f"{v:,.4f}"
    return f"{v:,.6g}"


def classify_sector(symbol: str, name: str) -> str:
    symbol = (symbol or "").upper()
    if symbol in SECTOR_MAP:
        return SECTOR_MAP[symbol]

    low = (name or "").lower()
    if "ai" in low:
        return "AI"
    if "meme" in low:
        return "Meme"
    if "swap" in low or "finance" in low:
        return "DeFi"
    if "bitcoin" in low or "eth" in low:
        return "Bluechip"
    return "General"


def opportunity_score(
    market_cap: float,
    fdv: float,
    volume: float,
    price: float,
    rank: int,
    is_major: bool,
) -> float:
    score = 0.0

    if 0 < fdv <= 25_000_000:
        score += 3.2
    elif fdv <= 75_000_000:
        score += 2.6
    elif fdv <= 150_000_000:
        score += 1.8
    elif fdv <= 500_000_000:
        score += 0.9

    if 0 < market_cap <= 25_000_000:
        score += 2.0
    elif market_cap <= 75_000_000:
        score += 1.6
    elif market_cap <= 150_000_000:
        score += 1.0

    if volume >= 100_000_000:
        score += 2.4
    elif volume >= 50_000_000:
        score += 2.0
    elif volume >= 15_000_000:
        score += 1.5
    elif volume >= 3_000_000:
        score += 1.0

    if price <= 5:
        score += 1.1
    elif price <= 25:
        score += 0.5

    if rank > 100:
        score += 0.8
    elif rank > 40:
        score += 0.4

    if is_major:
        score -= 1.8

    return round(clamp(score, 0, 10), 2)


def execution_score(
    price: float,
    snr: Dict[str, Any],
    impact_pct: float,
    volume_ratio: float,
) -> float:
    support_hi = safe_float((snr.get("supportZone") or [0, 0])[-1])
    breakout = safe_float(snr.get("breakoutLevel"))
    rr = safe_float(snr.get("rr"))
    trend = snr.get("trend", "neutral")

    if price <= 0:
        return 0.0

    dist_to_support_pct = abs(price - support_hi) / price * 100 if support_hi > 0 else 99
    dist_to_breakout_pct = abs(breakout - price) / price * 100 if breakout > 0 else 99

    score = 0.0

    if trend == "bullish":
        score += 3.0
    elif trend == "neutral":
        score += 1.5
    else:
        score += 0.5

    if dist_to_support_pct <= 2.5:
        score += 2.4
    elif dist_to_support_pct <= 5:
        score += 1.6
    elif dist_to_breakout_pct <= 2.5:
        score += 1.8
    elif dist_to_breakout_pct <= 5:
        score += 1.0

    if rr >= 2:
        score += 2.2
    elif rr >= 1.5:
        score += 1.6
    elif rr >= 1.2:
        score += 0.8

    if volume_ratio >= 1.5:
        score += 1.6
    elif volume_ratio >= 1.2:
        score += 1.2
    elif volume_ratio >= 1.0:
        score += 0.7

    if impact_pct >= 4:
        score += 1.2
    elif impact_pct >= 1:
        score += 0.9
    elif impact_pct >= 0.4:
        score += 0.5

    return round(clamp(score, 0, 10), 2)


def risk_score(
    market_cap: float,
    volume: float,
    tradable: bool,
    is_major: bool,
    sector: str,
) -> Tuple[str, float]:
    score = 0.0

    if is_major:
        score += 1.0
    elif market_cap >= 500_000_000:
        score += 2.0
    elif market_cap >= 150_000_000:
        score += 3.0
    elif market_cap >= 50_000_000:
        score += 4.5
    else:
        score += 6.5

    if volume >= 100_000_000:
        score -= 1.5
    elif volume >= 25_000_000:
        score -= 1.0
    elif volume >= 5_000_000:
        score -= 0.5

    if tradable:
        score -= 1.0

    if sector == "Meme":
        score += 1.0

    score = clamp(score, 1, 9)

    if score <= 3:
        return "Low", round(score, 2)
    if score <= 6:
        return "Medium", round(score, 2)
    return "High", round(score, 2)


def build_action_plan(
    symbol: str,
    name: str,
    market_row: Dict[str, Any],
    snr: Dict[str, Any],
    tradable: bool,
    exchange_text: str,
    rules: Dict[str, Any],
) -> Dict[str, Any]:
    market_cap = safe_float(market_row.get("market_cap"))
    fdv = safe_float(market_row.get("fully_diluted_valuation")) or market_cap
    volume = safe_float(market_row.get("total_volume"))
    price = safe_float(market_row.get("current_price"))
    rank = safe_int(market_row.get("market_cap_rank"), 999999)
    impact_pct = abs(safe_float(market_row.get("price_change_percentage_24h"), 0.0))
    direction = "Buy Pressure" if safe_float(market_row.get("price_change_percentage_24h"), 0.0) >= 0 else "Sell Pressure"

    is_major = symbol in MAJOR_SYMBOLS
    sector = classify_sector(symbol, name)

    opp = opportunity_score(market_cap, fdv, volume, price, rank, is_major)
    exe = execution_score(price, snr, impact_pct, safe_float(snr.get("volumeRatio"), 1.0))
    risk_label, risk_numeric = risk_score(market_cap, volume, tradable, is_major, sector)

    final_score = round(clamp((opp * 0.45) + (exe * 0.55), 0, 10), 2)

    support_zone = snr.get("supportZone", [0, 0])
    resistance_zone = snr.get("resistanceZone", [0, 0])
    invalidation = safe_float(snr.get("invalidation"))
    tp1 = safe_float(snr.get("tp1"))
    tp2 = safe_float(snr.get("tp2"))
    breakout = safe_float(snr.get("breakoutLevel"))
    rr = safe_float(snr.get("rr"))
    trend = snr.get("trend", "neutral")

    support_hi = safe_float(support_zone[-1] if support_zone else 0)
    resistance_lo = safe_float(resistance_zone[0] if resistance_zone else 0)

    near_support = price > 0 and support_hi > 0 and abs(price - support_hi) / price <= 0.03
    near_breakout = price > 0 and breakout > 0 and abs(price - breakout) / price <= 0.02

    action = "Keep On Watch"
    action_short = "WATCH"
    why = "Monitor for cleaner structure and confirmation."
    next_step = "Stay patient and watch for better alignment."
    do_not = "Do not force early entry."
    cancel_if = "Cancel if structure weakens further."

    if direction == "Sell Pressure" or trend == "bearish":
        action = "Reduce Risk"
        action_short = "REDUCE RISK"
        why = "Selling pressure or weak structure makes fresh long exposure less attractive."
        next_step = f"Avoid fresh long entry unless price reclaims {fmt_price(breakout) if breakout else 'the trigger zone'}."
        do_not = "Do not catch the dip blindly."
        cancel_if = f"Cancel caution only if price closes back above {fmt_price(breakout) if breakout else 'the resistance trigger'}."
    else:
        if near_support and rr >= safe_float(rules.get("buy_zone_rr_min"), 1.6) and trend in ("bullish", "neutral"):
            action = "Prepare Entry"
            action_short = "BUY ZONE"
            why = "Price is sitting near support with acceptable reward-to-risk."
            next_step = f"Best buy zone around {fmt_price(support_zone[0])} - {fmt_price(support_zone[-1])}. Enter only if buyers defend support."
            do_not = f"Do not hold if price loses {fmt_price(invalidation)}."
            cancel_if = f"Cancel if price breaks below {fmt_price(invalidation)}."
        elif near_breakout and rr >= safe_float(rules.get("wait_breakout_rr_min"), 1.3):
            action = "Wait Breakout"
            action_short = "WAIT BREAKOUT"
            why = "Price is close to a breakout trigger but still needs confirmation."
            next_step = f"Only act on 1H close above {fmt_price(breakout)} or breakout-retest hold."
            do_not = "Do not pre-chase before breakout confirmation."
            cancel_if = f"Cancel if rejection repeats under {fmt_price(breakout)}."
        elif final_score >= safe_float(rules.get("min_focus_score", 8.4)):
            action = "Prepare Entry"
            action_short = "WAIT FOR CONFIRMATION"
            why = "Strong relative activity with acceptable market context."
            next_step = f"Wait for reaction near support {fmt_price(support_zone[-1])} or clean move through {fmt_price(breakout)}."
            do_not = "Do not chase a vertical move."
            cancel_if = f"Cancel if price loses {fmt_price(invalidation)}."
        elif final_score >= safe_float(rules.get("min_emerging_score", 6.2)):
            action = "Keep On Watch"
            action_short = "WATCH"
            why = "Early momentum exists, but setup still needs cleaner confirmation."
            next_step = f"Watch retest near {fmt_price(support_zone[-1])} or strength above {fmt_price(breakout)}."
            do_not = "Do not size too big too early."
            cancel_if = f"Cancel if price breaks below {fmt_price(invalidation)}."
        else:
            action = "Keep On Watch"
            action_short = "WATCH"

    confidence = "High" if tradable and risk_label == "Low" else ("Medium" if tradable else "Low")

    return {
        "token": symbol,
        "name": name,
        "pair": f"{symbol}/USD",
        "sector": sector,
        "isMajor": is_major,
        "action": action,
        "actionShort": action_short,
        "confidence": confidence,
        "score": final_score,
        "opportunityScore": opp,
        "executionScore": exe,
        "risk": risk_label,
        "riskNumeric": risk_numeric,
        "direction": direction,
        "impactPct": round(impact_pct, 2),
        "tradeUsd": round(volume, 2),
        "liquidityUsd": round(market_cap, 2),
        "currentPrice": round(price, 8),
        "marketCap": round(market_cap, 2),
        "fdv": round(fdv, 2),
        "volume24h": round(volume, 2),
        "marketCapRank": rank,
        "why": why,
        "nextStep": next_step,
        "doNot": do_not,
        "cancelIf": cancel_if,
        "binanceTradable": tradable,
        "exchangeText": exchange_text,
        "supportZone": support_zone,
        "resistanceZone": resistance_zone,
        "entryAggressive": snr.get("entryAggressive"),
        "entryConfirmation": snr.get("entryConfirmation"),
        "breakoutLevel": snr.get("breakoutLevel"),
        "invalidation": invalidation,
        "tp1": tp1,
        "tp2": tp2,
        "rr": rr,
        "trend": trend,
        "history": snr.get("history", []),
    }
