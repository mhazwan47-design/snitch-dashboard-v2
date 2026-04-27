from __future__ import annotations

from typing import Any, Dict, Tuple


MAJOR_SYMBOLS = {
    "BTC", "ETH", "XRP", "BNB", "SOL", "DOGE", "TRX", "AAVE",
    "ADA", "LINK", "AVAX", "SUI", "TON", "BCH", "LTC", "ATOM",
    "APT", "FIL", "ALGO", "ARB", "OP", "ONDO", "UNI", "ICP",
    "NEAR", "DOT", "TAO", "XMR", "PEPE", "HYPE", "RENDER",
}

SECTOR_MAP = {
    "ARB": "L2",
    "OP": "L2",
    "ATOM": "Interoperability",
    "ONDO": "RWA",
    "DOGE": "Meme",
    "SHIB": "Meme",
    "PEPE": "Meme",
    "BONK": "Meme",
    "WIF": "Meme",
    "RENDER": "AI / Infra",
    "FET": "AI",
    "TAO": "AI",
    "PHB": "AI",
    "AIXBT": "AI",
    "AAVE": "DeFi",
    "UNI": "DeFi",
    "LQTY": "DeFi",
    "ORCA": "DeFi",
    "LINK": "Oracle",
    "ICP": "Infra",
    "TON": "Infra",
    "FIL": "Storage",
    "APT": "L1",
    "SUI": "L1",
    "ALGO": "L1",
    "NEAR": "L1",
    "AVAX": "L1",
    "DOT": "L1",
    "CORE": "L1",
    "MOVR": "L1",
    "SSV": "Infra",
    "PIXEL": "Gaming",
    "GAL": "Infra",
    "ENSO": "Infra",
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
    if v <= 0:
        return "N/A"
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
    if "game" in low:
        return "Gaming"
    if "storage" in low:
        return "Storage"
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

    if is_major:
        score += 3.2
    else:
        if 0 < fdv <= 20_000_000:
            score += 3.5
        elif fdv <= 50_000_000:
            score += 3.0
        elif fdv <= 100_000_000:
            score += 2.4
        elif fdv <= 180_000_000:
            score += 1.8
        elif fdv <= 300_000_000:
            score += 1.2
        elif fdv <= 600_000_000:
            score += 0.7

        if 0 < market_cap <= 20_000_000:
            score += 2.2
        elif market_cap <= 50_000_000:
            score += 1.8
        elif market_cap <= 120_000_000:
            score += 1.2
        elif market_cap <= 300_000_000:
            score += 0.8

    if volume >= 250_000_000:
        score += 2.8
    elif volume >= 100_000_000:
        score += 2.3
    elif volume >= 40_000_000:
        score += 1.8
    elif volume >= 10_000_000:
        score += 1.3
    elif volume >= 3_000_000:
        score += 0.9

    if price <= 5:
        score += 0.8
    elif price <= 25:
        score += 0.4

    if not is_major:
        if rank > 150:
            score += 0.9
        elif rank > 70:
            score += 0.5

    return round(clamp(score, 0, 10), 2)


def structure_metrics(price: float, snr: Dict[str, Any]) -> Dict[str, float]:
    support_zone = snr.get("supportZone", [0, 0]) or [0, 0]
    resistance_zone = snr.get("resistanceZone", [0, 0]) or [0, 0]

    support_lo = safe_float(support_zone[0])
    support_hi = safe_float(support_zone[-1])
    resistance_lo = safe_float(resistance_zone[0])
    resistance_hi = safe_float(resistance_zone[-1])
    breakout = safe_float(snr.get("breakoutLevel"))
    invalidation = safe_float(snr.get("invalidation"))
    tp1 = safe_float(snr.get("tp1"))
    tp2 = safe_float(snr.get("tp2"))

    if price <= 0:
        return {
            "dist_to_support_pct": 99.0,
            "dist_to_breakout_pct": 99.0,
            "room_to_resistance_pct": 0.0,
            "stop_pct": 0.0,
            "reward1_pct": 0.0,
            "reward2_pct": 0.0,
            "support_lo": support_lo,
            "support_hi": support_hi,
            "resistance_lo": resistance_lo,
            "resistance_hi": resistance_hi,
            "breakout": breakout,
            "invalidation": invalidation,
            "tp1": tp1,
            "tp2": tp2,
        }

    dist_to_support_pct = abs(price - support_hi) / price * 100 if support_hi > 0 else 99.0
    dist_to_breakout_pct = abs(breakout - price) / price * 100 if breakout > 0 else 99.0
    room_to_resistance_pct = abs(resistance_lo - price) / price * 100 if resistance_lo > 0 else 0.0
    stop_pct = abs(price - invalidation) / price * 100 if invalidation > 0 else 0.0
    reward1_pct = abs(tp1 - price) / price * 100 if tp1 > 0 else 0.0
    reward2_pct = abs(tp2 - price) / price * 100 if tp2 > 0 else 0.0

    return {
        "dist_to_support_pct": dist_to_support_pct,
        "dist_to_breakout_pct": dist_to_breakout_pct,
        "room_to_resistance_pct": room_to_resistance_pct,
        "stop_pct": stop_pct,
        "reward1_pct": reward1_pct,
        "reward2_pct": reward2_pct,
        "support_lo": support_lo,
        "support_hi": support_hi,
        "resistance_lo": resistance_lo,
        "resistance_hi": resistance_hi,
        "breakout": breakout,
        "invalidation": invalidation,
        "tp1": tp1,
        "tp2": tp2,
    }


def derive_rr(price: float, structure: Dict[str, float], trend: str) -> float:
    if price <= 0:
        return 1.0

    stop = abs(price - structure["invalidation"])
    if stop <= 0:
        stop = price * 0.02

    reward_1 = abs(structure["tp1"] - price) if structure["tp1"] > 0 else 0.0
    reward_2 = abs(structure["tp2"] - price) if structure["tp2"] > 0 else 0.0
    reward = max(reward_1, reward_2 * 0.85)

    rr = reward / stop if stop > 0 else 1.0

    if structure["dist_to_support_pct"] <= 2.4:
        rr += 0.35
    elif structure["dist_to_breakout_pct"] <= 1.8:
        rr += 0.18

    if trend == "bullish":
        rr += 0.10
    elif trend == "bearish":
        rr -= 0.10

    return round(clamp(rr, 1.02, 4.2), 2)


def execution_score(
    impact_pct: float,
    volume_ratio: float,
    trend: str,
    rr: float,
    structure: Dict[str, float],
) -> float:
    score = 0.0

    if trend == "bullish":
        score += 3.0
    elif trend == "neutral":
        score += 2.2
    else:
        score += 0.7

    if structure["dist_to_support_pct"] <= 1.5:
        score += 3.0
    elif structure["dist_to_support_pct"] <= 3.0:
        score += 2.3
    elif structure["dist_to_support_pct"] <= 5.0:
        score += 1.4
    elif structure["dist_to_breakout_pct"] <= 1.1:
        score += 2.2
    elif structure["dist_to_breakout_pct"] <= 2.3:
        score += 1.6
    elif structure["dist_to_breakout_pct"] <= 4.0:
        score += 0.9

    if rr >= 2.2:
        score += 2.3
    elif rr >= 1.8:
        score += 1.9
    elif rr >= 1.5:
        score += 1.4
    elif rr >= 1.3:
        score += 0.95
    elif rr >= 1.15:
        score += 0.45

    if volume_ratio >= 1.8:
        score += 1.3
    elif volume_ratio >= 1.3:
        score += 1.0
    elif volume_ratio >= 1.0:
        score += 0.7

    if impact_pct >= 10:
        score += 0.9
    elif impact_pct >= 5:
        score += 0.75
    elif impact_pct >= 2:
        score += 0.55
    elif impact_pct >= 0.8:
        score += 0.25

    if structure["room_to_resistance_pct"] >= 7:
        score += 0.7
    elif structure["room_to_resistance_pct"] >= 4:
        score += 0.4

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
        score += 2.2
    elif market_cap >= 400_000_000:
        score += 3.0
    elif market_cap >= 150_000_000:
        score += 3.9
    elif market_cap >= 60_000_000:
        score += 4.9
    elif market_cap >= 20_000_000:
        score += 5.8
    else:
        score += 6.8

    if volume >= 150_000_000:
        score -= 1.4
    elif volume >= 50_000_000:
        score -= 1.0
    elif volume >= 10_000_000:
        score -= 0.6

    if tradable:
        score -= 1.0

    if sector == "Meme":
        score += 0.8

    score = clamp(score, 1, 9)

    if score <= 3.2:
        return "Low", round(score, 2)
    if score <= 5.9:
        return "Medium", round(score, 2)
    return "High", round(score, 2)


def cheap_reason(symbol: str, sector: str, market_cap: float, fdv: float, price: float, is_major: bool) -> str:
    if is_major:
        parts = ["high-liquidity major"]
        if sector and sector != "General":
            parts.append(f"{sector} narrative")
        if price <= 50:
            parts.append("cleaner execution access")
        return ", ".join(parts)

    reasons = []
    if 0 < fdv <= 50_000_000:
        reasons.append("low FDV")
    elif fdv <= 120_000_000:
        reasons.append("manageable FDV")

    if 0 < market_cap <= 50_000_000:
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


def detect_setup_label(
    direction: str,
    is_major: bool,
    final_score: float,
    rr: float,
    impact_pct: float,
    volume: float,
    structure: Dict[str, float],
    trend: str,
) -> Tuple[str, str, bool, str]:
    near_support = structure["dist_to_support_pct"] <= 2.4
    near_breakout = structure["dist_to_breakout_pct"] <= 1.8
    extended = structure["dist_to_support_pct"] >= 8.5
    strong_momentum = impact_pct >= 2.0
    strong_volume = volume >= 10_000_000
    decent_volume = volume >= 3_000_000

    if direction == "Sell Pressure":
        if is_major:
            return "REDUCE RISK", "Major Risk-off", False, "caution"
        return "REDUCE RISK", "Avoid / Risk-off", False, "caution"

    if is_major:
        if near_support and rr >= 1.25:
            return "MAJOR BUY ZONE", "Major Retest Buy", True, "focus"
        if near_breakout and rr >= 1.20:
            return "MAJOR BREAKOUT", "Major Breakout Trigger", False, "focus"
        if extended and strong_momentum:
            return "WAIT FOR RETEST", "Major Retest Needed", False, "focus"
        return "WATCH MAJOR", "Major Monitor", False, "emerging"

    if near_support and rr >= 1.65 and strong_momentum and decent_volume:
        return "BUY NOW", "Retest Buy Zone", True, "focus"

    if near_support and rr >= 1.40 and strong_momentum and decent_volume:
        return "BUY ON RETEST", "Retest Buy", True, "focus"

    if near_breakout and rr >= 1.35 and strong_momentum:
        return "WAIT BREAKOUT", "Breakout Trigger", False, "focus"

    if extended and strong_momentum and final_score >= 7.0:
        return "WAIT FOR RETEST", "Retest Needed", False, "focus"

    if final_score >= 7.0 and (strong_momentum or strong_volume):
        return "WAIT FOR CONFIRMATION", "Confirmation Entry", False, "focus"

    if final_score >= 5.8 and (strong_momentum or strong_volume):
        return "EARLY MOMENTUM", "Early Momentum", False, "emerging"

    return "WATCH", "Watchlist", False, "emerging"


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
    trend = str(snr.get("trend", "neutral")).lower()
    volume_ratio = safe_float(snr.get("volumeRatio"), 1.0)

    structure = structure_metrics(price, snr)
    rr = derive_rr(price, structure, trend)
    opp = opportunity_score(market_cap, fdv, volume, price, rank, is_major)
    exe = execution_score(impact_pct, volume_ratio, trend, rr, structure)
    risk_label, risk_numeric = risk_score(market_cap, volume, tradable, is_major, sector)

    final_score = round(clamp((opp * 0.40) + (exe * 0.60), 0, 10), 2)

    action_short, entry_type, execution_ready, focus_bucket = detect_setup_label(
        direction=direction,
        is_major=is_major,
        final_score=final_score,
        rr=rr,
        impact_pct=impact_pct,
        volume=volume,
        structure=structure,
        trend=trend,
    )

    action = {
        "BUY NOW": "Prepare Entry",
        "BUY ON RETEST": "Prepare Entry",
        "WAIT BREAKOUT": "Wait Breakout",
        "WAIT FOR RETEST": "Keep On Watch",
        "WAIT FOR CONFIRMATION": "Prepare Entry",
        "EARLY MOMENTUM": "Keep On Watch",
        "WATCH": "Keep On Watch",
        "REDUCE RISK": "Reduce Risk",
        "MAJOR BUY ZONE": "Prepare Entry",
        "MAJOR BREAKOUT": "Wait Breakout",
        "WATCH MAJOR": "Keep On Watch",
    }.get(action_short, "Keep On Watch")

    trap_reason = ""
    why = "Monitor for cleaner structure and confirmation."
    next_step = "Wait for retest support or breakout confirmation."
    do_not = "Do not force early entry."
    cancel_if = "Cancel the setup if structure degrades."

    if action_short == "REDUCE RISK":
        why = "Selling pressure is currently dominating this structure."
        next_step = f"Wait for reclaim above {fmt_price(structure['breakout'])} before considering fresh long bias."
        do_not = "Do not catch the dip blindly."
        cancel_if = f"Cancel caution only if price reclaims and holds above {fmt_price(structure['breakout'])}."
        trap_reason = "sell pressure / weak structure"

    elif action_short == "BUY NOW":
        why = "Price is sitting near support with stronger reward-to-risk and usable structure now."
        next_step = f"Best zone now is around {fmt_price(structure['support_lo'])} - {fmt_price(structure['support_hi'])}. Confirm with a hold."
        do_not = f"Do not hold if price loses {fmt_price(structure['invalidation'])}."
        cancel_if = f"Cancel if price breaks below {fmt_price(structure['invalidation'])}."

    elif action_short == "BUY ON RETEST":
        why = "Price is close enough to support to prepare for a cleaner retest entry."
        next_step = f"Wait for reaction around {fmt_price(structure['support_lo'])} - {fmt_price(structure['support_hi'])}."
        do_not = "Do not front-run before support reacts."
        cancel_if = f"Cancel if support fails below {fmt_price(structure['invalidation'])}."

    elif action_short == "WAIT BREAKOUT":
        why = "Structure is pressing resistance and becomes better only after breakout confirmation."
        next_step = f"Enter only on strong close above {fmt_price(structure['breakout'])} or breakout-retest hold."
        do_not = "Do not buy directly under resistance."
        cancel_if = f"Cancel if breakout keeps failing under {fmt_price(structure['breakout'])}."

    elif action_short == "WAIT FOR RETEST":
        why = "Momentum exists, but price is stretched and a cleaner reset is better."
        next_step = f"Wait for pullback nearer {fmt_price(structure['support_hi'])}."
        do_not = "Do not chase extended move."
        cancel_if = f"Cancel if retest loses {fmt_price(structure['invalidation'])}."
        trap_reason = "extended from support"

    elif action_short == "WAIT FOR CONFIRMATION":
        why = "Relative activity is strong enough to monitor closely, but confirmation is still needed."
        next_step = f"Watch support defense near {fmt_price(structure['support_hi'])} or break above {fmt_price(structure['breakout'])}."
        do_not = "Do not size big before confirmation."
        cancel_if = f"Cancel if price loses {fmt_price(structure['invalidation'])}."

    elif action_short == "EARLY MOMENTUM":
        why = "Momentum is building, but setup is still early and not yet clean enough for higher conviction."
        next_step = f"Watch retest near {fmt_price(structure['support_hi'])} or breakout above {fmt_price(structure['breakout'])}."
        do_not = "Do not size too big too early."
        cancel_if = f"Cancel if price breaks below {fmt_price(structure['invalidation'])}."

    elif action_short == "WATCH":
        why = "Some potential exists, but the setup is not yet clean enough."
        next_step = f"Wait for either retest nearer {fmt_price(structure['support_hi'])} or better breakout behavior above {fmt_price(structure['breakout'])}."
        do_not = "Do not rush entry on weak structure."
        cancel_if = f"Cancel if price loses {fmt_price(structure['invalidation'])}."
        trap_reason = "not enough clean edge"

    elif action_short == "MAJOR BUY ZONE":
        why = "Major coin is near support with cleaner liquidity and better execution quality."
        next_step = f"Watch reaction around {fmt_price(structure['support_lo'])} - {fmt_price(structure['support_hi'])} for confirmation."
        do_not = f"Do not hold if price loses {fmt_price(structure['invalidation'])}."
        cancel_if = f"Cancel if price breaks below {fmt_price(structure['invalidation'])}."

    elif action_short == "MAJOR BREAKOUT":
        why = "Major coin is near breakout level and can guide overall market tone."
        next_step = f"Enter only on strong close above {fmt_price(structure['breakout'])}."
        do_not = "Do not pre-buy under resistance."
        cancel_if = f"Cancel if breakout fails below {fmt_price(structure['breakout'])}."

    elif action_short == "WATCH MAJOR":
        why = "Useful as higher-liquidity market guide and execution reference."
        next_step = f"Watch support near {fmt_price(structure['support_hi'])} or breakout above {fmt_price(structure['breakout'])}."
        do_not = "Do not assume major always means best upside."
        cancel_if = f"Cancel if price loses {fmt_price(structure['invalidation'])}."

    confidence = "Low"
    if tradable and risk_label == "Low":
        confidence = "High"
    elif tradable or risk_label == "Medium":
        confidence = "Medium"

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
        "whyCheap": cheap_reason(symbol, sector, market_cap, fdv, price, is_major),
        "nextStep": next_step,
        "doNot": do_not,
        "cancelIf": cancel_if,
        "trapReason": trap_reason,
        "binanceTradable": tradable,
        "exchangeText": exchange_text,
        "supportZone": snr.get("supportZone", [0, 0]),
        "resistanceZone": snr.get("resistanceZone", [0, 0]),
        "buyZone": snr.get("supportZone", [0, 0]),
        "entryAggressive": snr.get("entryAggressive"),
        "entryConfirmation": snr.get("entryConfirmation"),
        "breakoutLevel": structure["breakout"],
        "breakoutTrigger": structure["breakout"],
        "invalidation": structure["invalidation"],
        "tp1": structure["tp1"],
        "tp2": structure["tp2"],
        "rr": rr,
        "trend": trend,
        "history": snr.get("history", []),
    }
