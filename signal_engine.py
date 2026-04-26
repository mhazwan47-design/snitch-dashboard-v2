from __future__ import annotations

from typing import Any, Dict, Tuple


MAJOR_SYMBOLS = {
    "BTC", "ETH", "XRP", "BNB", "SOL", "DOGE", "TRX", "AAVE",
    "ADA", "LINK", "AVAX", "SUI", "TON", "BCH", "LTC", "ATOM",
    "APT", "FIL", "ALGO", "ARB", "OP", "ONDO"
}

SECTOR_MAP = {
    "ARB": "L2",
    "OP": "L2",
    "ATOM": "Interoperability",
    "ONDO": "RWA",
    "TRUMP": "Meme",
    "DOGE": "Meme",
    "SHIB": "Meme",
    "PEPE": "Meme",
    "RENDER": "AI / Infra",
    "FET": "AI",
    "FIL": "Storage",
    "AAVE": "DeFi",
    "UNI": "DeFi",
    "LINK": "Oracle",
    "ICP": "Infra",
    "TON": "Infra",
    "APT": "L1",
    "SUI": "L1",
    "ALGO": "L1",
    "ARB": "L2",
    "STG": "Bridge",
    "GLMR": "L1",
    "PHB": "AI",
    "ORDI": "Bitcoin Ecosystem",
    "BLUR": "NFT",
    "MOVR": "L1",
    "CORE": "L1"
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
    if "oracle" in low:
        return "Oracle"
    if "chain" in low:
        return "Infra"
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

    if 0 < fdv <= 20_000_000:
        score += 3.4
    elif fdv <= 50_000_000:
        score += 2.9
    elif fdv <= 100_000_000:
        score += 2.2
    elif fdv <= 180_000_000:
        score += 1.4
    elif fdv <= 500_000_000:
        score += 0.7

    if 0 < market_cap <= 20_000_000:
        score += 2.1
    elif market_cap <= 50_000_000:
        score += 1.8
    elif market_cap <= 120_000_000:
        score += 1.2
    elif market_cap <= 250_000_000:
        score += 0.6

    if volume >= 120_000_000:
        score += 2.5
    elif volume >= 60_000_000:
        score += 2.0
    elif volume >= 20_000_000:
        score += 1.5
    elif volume >= 5_000_000:
        score += 1.0
    elif volume >= 2_500_000:
        score += 0.6

    if price <= 5:
        score += 1.0
    elif price <= 20:
        score += 0.5

    if rank > 150:
        score += 0.9
    elif rank > 70:
        score += 0.5

    if is_major:
        score -= 1.6

    return round(clamp(score, 0, 10), 2)


def execution_score(
    price: float,
    snr: Dict[str, Any],
    impact_pct: float,
    volume_ratio: float,
) -> float:
    support_zone = snr.get("supportZone", [0, 0])
    resistance_zone = snr.get("resistanceZone", [0, 0])

    support_hi = safe_float(support_zone[-1] if support_zone else 0)
    resistance_lo = safe_float(resistance_zone[0] if resistance_zone else 0)
    breakout = safe_float(snr.get("breakoutLevel"))
    rr = safe_float(snr.get("rr"))
    trend = snr.get("trend", "neutral")

    if price <= 0:
        return 0.0

    dist_to_support_pct = abs(price - support_hi) / price * 100 if support_hi > 0 else 99
    dist_to_breakout_pct = abs(breakout - price) / price * 100 if breakout > 0 else 99
    dist_to_resistance_pct = abs(resistance_lo - price) / price * 100 if resistance_lo > 0 else 99

    score = 0.0

    if trend == "bullish":
        score += 3.1
    elif trend == "neutral":
        score += 1.7
    else:
        score += 0.5

    if dist_to_support_pct <= 2.2:
        score += 2.5
    elif dist_to_support_pct <= 4.5:
        score += 1.8
    elif dist_to_breakout_pct <= 1.8:
        score += 2.0
    elif dist_to_breakout_pct <= 3.8:
        score += 1.3
    elif dist_to_resistance_pct <= 1.5:
        score -= 0.9

    if rr >= 2.2:
        score += 2.4
    elif rr >= 1.7:
        score += 1.8
    elif rr >= 1.3:
        score += 1.0
    elif rr >= 1.0:
        score += 0.3

    if volume_ratio >= 1.6:
        score += 1.4
    elif volume_ratio >= 1.2:
        score += 1.1
    elif volume_ratio >= 1.0:
        score += 0.7

    if impact_pct >= 5:
        score += 1.0
    elif impact_pct >= 2:
        score += 0.8
    elif impact_pct >= 0.8:
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
        score += 1.4
    elif market_cap >= 400_000_000:
        score += 2.3
    elif market_cap >= 150_000_000:
        score += 3.2
    elif market_cap >= 60_000_000:
        score += 4.4
    elif market_cap >= 20_000_000:
        score += 5.5
    else:
        score += 6.7

    if volume >= 120_000_000:
        score -= 1.4
    elif volume >= 40_000_000:
        score -= 1.0
    elif volume >= 8_000_000:
        score -= 0.6

    if tradable:
        score -= 1.2

    if sector == "Meme":
        score += 1.0

    score = clamp(score, 1, 9)

    if score <= 3.1:
        return "Low", round(score, 2)
    if score <= 5.8:
        return "Medium", round(score, 2)
    return "High", round(score, 2)


def cheap_reason(symbol: str, sector: str, market_cap: float, fdv: float, price: float) -> str:
    reasons = []
    if fdv > 0 and fdv <= 50_000_000:
        reasons.append("low FDV")
    elif fdv <= 120_000_000:
        reasons.append("manageable FDV")

    if market_cap > 0 and market_cap <= 50_000_000:
        reasons.append("still early by market cap")
    elif market_cap <= 120_000_000:
        reasons.append("not too crowded yet")

    if price <= 5:
        reasons.append("price still accessible")

    if sector and sector != "General":
        reasons.append(f"{sector} narrative")

    if not reasons:
        return "valuation still reasonable with room if structure confirms"
    return ", ".join(reasons[:3])


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
    raw_change = safe_float(market_row.get("price_change_percentage_24h"), 0.0)
    impact_pct = abs(raw_change)
    direction = "Buy Pressure" if raw_change >= 0 else "Sell Pressure"

    is_major = symbol in MAJOR_SYMBOLS
    sector = classify_sector(symbol, name)

    opp = opportunity_score(market_cap, fdv, volume, price, rank, is_major)
    exe = execution_score(price, snr, impact_pct, safe_float(snr.get("volumeRatio"), 1.0))
    risk_label, risk_numeric = risk_score(market_cap, volume, tradable, is_major, sector)
    final_score = round(clamp((opp * 0.42) + (exe * 0.58), 0, 10), 2)

    support_zone = snr.get("supportZone", [0, 0])
    resistance_zone = snr.get("resistanceZone", [0, 0])
    invalidation = safe_float(snr.get("invalidation"))
    tp1 = safe_float(snr.get("tp1"))
    tp2 = safe_float(snr.get("tp2"))
    breakout = safe_float(snr.get("breakoutLevel"))
    rr = safe_float(snr.get("rr"))
    trend = snr.get("trend", "neutral")

    support_hi = safe_float(support_zone[-1] if support_zone else 0)
    support_lo = safe_float(support_zone[0] if support_zone else 0)
    resistance_lo = safe_float(resistance_zone[0] if resistance_zone else 0)

    near_support = price > 0 and support_hi > 0 and abs(price - support_hi) / price <= 0.032
    near_breakout = price > 0 and breakout > 0 and abs(price - breakout) / price <= 0.022
    too_extended = price > 0 and support_hi > 0 and ((price - support_hi) / price * 100) > safe_float(rules.get("max_extended_distance_pct", 12))
    clean_rr = rr >= safe_float(rules.get("buy_zone_rr_min", 1.5))

    action = "Keep On Watch"
    action_short = "WATCH"
    entry_type = "Watchlist"
    why = "Monitor for cleaner structure and confirmation."
    next_step = "Stay patient and wait for either retest support or breakout confirmation."
    do_not = "Do not force early entry."
    cancel_if = "Cancel the setup if structure degrades."
    execution_ready = False
    trap_reason = ""
    focus_bucket = "emerging"

    if direction == "Sell Pressure" or trend == "bearish":
        action = "Reduce Risk"
        action_short = "REDUCE RISK"
        entry_type = "Avoid / Risk-off"
        why = "Selling pressure or weak structure makes fresh long exposure less attractive."
        next_step = f"Avoid fresh long entry unless price reclaims {fmt_price(breakout) if breakout else 'the trigger zone'}."
        do_not = "Do not catch the dip blindly."
        cancel_if = f"Cancel caution only if price closes back above {fmt_price(breakout) if breakout else 'the trigger level'}."
        trap_reason = "bearish structure / sell pressure"
        focus_bucket = "caution"
    else:
        if near_support and clean_rr and trend in ("bullish", "neutral"):
            action = "Prepare Entry"
            action_short = "BUY ZONE"
            entry_type = "Retest Buy Zone"
            why = "Price is near support with acceptable reward-to-risk and usable structure."
            next_step = f"Best buy zone around {fmt_price(support_lo)} - {fmt_price(support_hi)}. Wait for support defense."
            do_not = f"Do not hold if price loses {fmt_price(invalidation)}."
            cancel_if = f"Cancel if price breaks below {fmt_price(invalidation)}."
            execution_ready = True
            focus_bucket = "focus"
        elif near_breakout and rr >= safe_float(rules.get("wait_breakout_rr_min", 1.25)):
            action = "Wait Breakout"
            action_short = "WAIT BREAKOUT"
            entry_type = "Breakout Trigger"
            why = "Price is near breakout level and can become actionable only after confirmation."
            next_step = f"Enter only on strong close above {fmt_price(breakout)} or breakout-retest hold."
            do_not = "Do not pre-buy under resistance."
            cancel_if = f"Cancel if repeated rejection happens below {fmt_price(breakout)}."
            focus_bucket = "focus" if final_score >= safe_float(rules.get("min_focus_score", 8.0)) else "emerging"
        elif too_extended and final_score >= safe_float(rules.get("min_focus_score", 8.0)):
            action = "Keep On Watch"
            action_short = "WAIT FOR RETEST"
            entry_type = "Retest Needed"
            why = "Momentum is strong, but price is extended from support and needs a cleaner retest."
            next_step = f"Do not chase. Wait for pullback closer to {fmt_price(support_hi)}."
            do_not = "Do not enter after an extended move."
            cancel_if = f"Cancel if pullback loses {fmt_price(invalidation)}."
            trap_reason = "extended from support"
            focus_bucket = "focus"
        elif final_score >= safe_float(rules.get("min_focus_score", 8.0)):
            action = "Prepare Entry"
            action_short = "WAIT FOR CONFIRMATION"
            entry_type = "Confirmation Entry"
            why = "Strong relative activity with acceptable market context."
            next_step = f"Wait for confirmation near support {fmt_price(support_hi)} or clean move above {fmt_price(breakout)}."
            do_not = "Do not chase a vertical move."
            cancel_if = f"Cancel if price loses {fmt_price(invalidation)}."
            focus_bucket = "focus"
        elif final_score >= safe_float(rules.get("min_emerging_score", 5.8)):
            action = "Keep On Watch"
            action_short = "WATCH"
            entry_type = "Early Watch"
            why = "Early momentum exists, but setup still needs cleaner confirmation."
            next_step = f"Watch retest near {fmt_price(support_hi)} or strength above {fmt_price(breakout)}."
            do_not = "Do not size too big too early."
            cancel_if = f"Cancel if price breaks below {fmt_price(invalidation)}."
            focus_bucket = "emerging"
        else:
            trap_reason = "not enough clean edge"

    confidence = "High" if tradable and risk_label == "Low" else ("Medium" if tradable else "Low")

    return {
        "token": symbol,
        "name": name,
        "pair": f"{symbol}/USD",
        "sector": sector,
        "isMajor": is_major,
        "action": action,
        "actionShort": action_short,
        "entryType": entry_type,
        "executionReady": execution_ready,
        "focusBucket": focus_bucket,
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
        "whyCheap": cheap_reason(symbol, sector, market_cap, fdv, price),
        "nextStep": next_step,
        "doNot": do_not,
        "cancelIf": cancel_if,
        "trapReason": trap_reason,
        "binanceTradable": tradable,
        "exchangeText": exchange_text,
        "supportZone": support_zone,
        "resistanceZone": resistance_zone,
        "buyZone": support_zone,
        "entryAggressive": snr.get("entryAggressive"),
        "entryConfirmation": snr.get("entryConfirmation"),
        "breakoutLevel": snr.get("breakoutLevel"),
        "breakoutTrigger": snr.get("breakoutLevel"),
        "invalidation": invalidation,
        "tp1": tp1,
        "tp2": tp2,
        "rr": rr,
        "trend": trend,
        "history": snr.get("history", []),
    }
