from __future__ import annotations

from typing import Any, Dict, Tuple


MAJOR_SYMBOLS = {
    "BTC", "ETH", "XRP", "BNB", "SOL", "DOGE", "TRX", "AAVE",
    "ADA", "LINK", "AVAX", "SUI", "TON", "BCH", "LTC", "ATOM",
    "APT", "FIL", "ALGO", "ARB", "OP", "ONDO", "UNI", "ICP",
    "NEAR", "DOT", "TAO", "XMR", "PEPE", "HYPE"
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
    "ORCA": "DeFi",
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
        score += 3.0
    else:
        if 0 < fdv <= 20_000_000:
            score += 3.4
        elif fdv <= 50_000_000:
            score += 2.9
        elif fdv <= 100_000_000:
            score += 2.3
        elif fdv <= 180_000_000:
            score += 1.8
        elif fdv <= 300_000_000:
            score += 1.2
        elif fdv <= 600_000_000:
            score += 0.6

        if 0 < market_cap <= 20_000_000:
            score += 2.1
        elif market_cap <= 50_000_000:
            score += 1.7
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
        score += 1.2
    elif volume >= 3_000_000:
        score += 0.8

    if price <= 5:
        score += 0.9
    elif price <= 25:
        score += 0.4

    if not is_major:
        if rank > 150:
            score += 0.9
        elif rank > 70:
            score += 0.5

    return round(clamp(score, 0, 10), 2)


def execution_score(
    price: float,
    snr: Dict[str, Any],
    impact_pct: float,
    volume_ratio: float,
) -> float:
    support_zone = snr.get("supportZone", [0, 0])
    resistance_zone = snr.get("resistanceZone", [0, 0])

    support_lo = safe_float(support_zone[0] if support_zone else 0)
    support_hi = safe_float(support_zone[-1] if support_zone else 0)
    resistance_lo = safe_float(resistance_zone[0] if resistance_zone else 0)
    breakout = safe_float(snr.get("breakoutLevel"))
    rr = safe_float(snr.get("rr"))
    trend = str(snr.get("trend", "neutral")).lower()

    if price <= 0:
        return 0.0

    dist_to_support_pct = abs(price - support_hi) / price * 100 if support_hi > 0 else 99
    dist_to_breakout_pct = abs(breakout - price) / price * 100 if breakout > 0 else 99
    room_to_resistance_pct = abs(resistance_lo - price) / price * 100 if resistance_lo > 0 else 0

    score = 0.0

    if trend == "bullish":
        score += 3.0
    elif trend == "neutral":
        score += 2.1
    else:
        score += 0.6

    if dist_to_support_pct <= 1.6:
        score += 2.8
    elif dist_to_support_pct <= 3.2:
        score += 2.2
    elif dist_to_support_pct <= 5.5:
        score += 1.4
    elif dist_to_breakout_pct <= 1.2:
        score += 2.2
    elif dist_to_breakout_pct <= 2.6:
        score += 1.6
    elif dist_to_breakout_pct <= 4.5:
        score += 0.9

    if rr >= 2.2:
        score += 2.4
    elif rr >= 1.8:
        score += 2.0
    elif rr >= 1.5:
        score += 1.5
    elif rr >= 1.3:
        score += 1.0
    elif rr >= 1.1:
        score += 0.5

    if volume_ratio >= 1.8:
        score += 1.3
    elif volume_ratio >= 1.3:
        score += 1.0
    elif volume_ratio >= 1.0:
        score += 0.7

    if impact_pct >= 8:
        score += 0.8
    elif impact_pct >= 4:
        score += 0.7
    elif impact_pct >= 1.5:
        score += 0.5

    if room_to_resistance_pct >= 6:
        score += 0.7
    elif room_to_resistance_pct >= 3:
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


def derive_rr(
    price: float,
    support_hi: float,
    breakout: float,
    invalidation: float,
    tp1: float,
    tp2: float,
    trend: str,
) -> float:
    if price <= 0:
        return 1.0

    stop = abs(price - invalidation)
    if stop <= 0:
        stop = price * 0.02

    reward_1 = abs(tp1 - price) if tp1 > 0 else 0.0
    reward_2 = abs(tp2 - price) if tp2 > 0 else 0.0
    reward = max(reward_1, reward_2 * 0.8)

    rr = reward / stop if stop > 0 else 1.0

    near_support = support_hi > 0 and abs(price - support_hi) / price <= 0.03
    near_breakout = breakout > 0 and abs(price - breakout) / price <= 0.025

    if near_support:
        rr += 0.35
    elif near_breakout:
        rr += 0.18

    if trend == "bullish":
        rr += 0.10
    elif trend == "bearish":
        rr -= 0.10

    return round(clamp(rr, 1.05, 3.5), 2)


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

    support_zone = snr.get("supportZone", [0, 0])
    resistance_zone = snr.get("resistanceZone", [0, 0])

    support_lo = safe_float(support_zone[0] if support_zone else 0)
    support_hi = safe_float(support_zone[-1] if support_zone else 0)
    resistance_lo = safe_float(resistance_zone[0] if resistance_zone else 0)
    resistance_hi = safe_float(resistance_zone[-1] if resistance_zone else 0)

    breakout = safe_float(snr.get("breakoutLevel"))
    invalidation = safe_float(snr.get("invalidation"))
    tp1 = safe_float(snr.get("tp1"))
    tp2 = safe_float(snr.get("tp2"))
    trend = str(snr.get("trend", "neutral")).lower()
    volume_ratio = safe_float(snr.get("volumeRatio"), 1.0)

    rr = derive_rr(price, support_hi, breakout, invalidation, tp1, tp2, trend)

    snr = {
        **snr,
        "rr": rr,
        "tp1": tp1,
        "tp2": tp2,
        "supportZone": support_zone,
        "resistanceZone": resistance_zone,
    }

    opp = opportunity_score(market_cap, fdv, volume, price, rank, is_major)
    exe = execution_score(price, snr, impact_pct, volume_ratio)
    risk_label, risk_numeric = risk_score(market_cap, volume, tradable, is_major, sector)

    final_score = round(clamp((opp * 0.42) + (exe * 0.58), 0, 10), 2)

    near_support = price > 0 and support_hi > 0 and abs(price - support_hi) / price <= 0.035
    near_breakout = price > 0 and breakout > 0 and abs(price - breakout) / price <= 0.025
    extended_from_support = price > 0 and support_hi > 0 and ((price - support_hi) / price * 100) > safe_float(rules.get("max_extended_distance_pct", 11.0))
    strong_momentum = impact_pct >= safe_float(rules.get("strong_momentum_pct", 2.5))
    decent_volume = volume >= safe_float(rules.get("min_decent_volume_usd", 3_000_000))
    strong_volume = volume >= safe_float(rules.get("min_strong_volume_usd", 10_000_000))

    action = "Keep On Watch"
    action_short = "WATCH"
    entry_type = "Watchlist"
    why = "Monitor for cleaner structure and confirmation."
    next_step = "Wait for retest support or breakout confirmation."
    do_not = "Do not force early entry."
    cancel_if = "Cancel the setup if structure degrades."
    execution_ready = False
    trap_reason = ""
    focus_bucket = "emerging"

    if direction == "Sell Pressure":
        action = "Reduce Risk"
        action_short = "REDUCE RISK"
        entry_type = "Avoid / Risk-off"
        why = "Selling pressure is currently dominating this structure."
        next_step = f"Wait for reclaim above {fmt_price(breakout)} before considering fresh long bias."
        do_not = "Do not catch the dip blindly."
        cancel_if = f"Cancel caution only if price reclaims and holds above {fmt_price(breakout)}."
        trap_reason = "sell pressure / weak structure"
        focus_bucket = "caution"

        if is_major:
            entry_type = "Major Risk-off"
            why = "Major coin is under selling pressure; use it as market tone, not fresh long aggression."
            focus_bucket = "major"

    else:
        if is_major:
            focus_bucket = "major"

            if near_support and rr >= 1.35 and strong_volume:
                action = "Prepare Entry"
                action_short = "MAJOR BUY ZONE"
                entry_type = "Major Retest Buy"
                why = "Major coin is near support with cleaner liquidity and better execution quality."
                next_step = f"Watch reaction around {fmt_price(support_lo)} - {fmt_price(support_hi)} for confirmation."
                do_not = f"Do not hold if price loses {fmt_price(invalidation)}."
                cancel_if = f"Cancel if price breaks below {fmt_price(invalidation)}."
                execution_ready = True
            elif near_breakout and rr >= 1.25:
                action = "Wait Breakout"
                action_short = "MAJOR BREAKOUT"
                entry_type = "Major Breakout Trigger"
                why = "Major coin is near breakout level and can guide overall market tone."
                next_step = f"Enter only on strong close above {fmt_price(breakout)}."
                do_not = "Do not pre-buy under resistance."
                cancel_if = f"Cancel if breakout fails below {fmt_price(breakout)}."
            elif extended_from_support and strong_momentum:
                action = "Keep On Watch"
                action_short = "WAIT FOR RETEST"
                entry_type = "Major Retest Needed"
                why = "Momentum exists, but price is stretched away from support."
                next_step = f"Wait for pullback nearer {fmt_price(support_hi)}."
                do_not = "Do not chase an extended major."
                cancel_if = f"Cancel if pullback loses {fmt_price(invalidation)}."
                trap_reason = "extended major"
            else:
                action = "Keep On Watch"
                action_short = "WATCH MAJOR"
                entry_type = "Major Monitor"
                why = "Useful as higher-liquidity market guide and execution reference."
                next_step = f"Watch support near {fmt_price(support_hi)} or breakout above {fmt_price(breakout)}."
                do_not = "Do not assume major always means best upside."
                cancel_if = f"Cancel if price loses {fmt_price(invalidation)}."

        else:
            if near_support and rr >= 1.55 and strong_momentum and decent_volume:
                action = "Prepare Entry"
                action_short = "BUY ZONE"
                entry_type = "Retest Buy Zone"
                why = "Price is near support with acceptable reward-to-risk and usable structure."
                next_step = f"Best buy zone around {fmt_price(support_lo)} - {fmt_price(support_hi)} with confirmation candle."
                do_not = f"Do not hold if price loses {fmt_price(invalidation)}."
                cancel_if = f"Cancel if price breaks below {fmt_price(invalidation)}."
                execution_ready = True
                focus_bucket = "focus"

            elif near_breakout and rr >= 1.35 and strong_momentum:
                action = "Wait Breakout"
                action_short = "WAIT BREAKOUT"
                entry_type = "Breakout Trigger"
                why = "Price is pressing resistance and can become actionable after confirmation."
                next_step = f"Enter only on strong close above {fmt_price(breakout)} or breakout-retest hold."
                do_not = "Do not pre-buy right under resistance."
                cancel_if = f"Cancel if breakout repeatedly fails under {fmt_price(breakout)}."
                focus_bucket = "focus"

            elif extended_from_support and strong_momentum and final_score >= 7.0:
                action = "Keep On Watch"
                action_short = "WAIT FOR RETEST"
                entry_type = "Retest Needed"
                why = "Momentum is strong, but price is extended from support and needs cleaner reset."
                next_step = f"Wait for pullback nearer {fmt_price(support_hi)}."
                do_not = "Do not chase extended move."
                cancel_if = f"Cancel if pullback loses {fmt_price(invalidation)}."
                trap_reason = "extended from support"
                focus_bucket = "focus"

            elif final_score >= 7.2 and strong_momentum and decent_volume:
                action = "Prepare Entry"
                action_short = "WAIT FOR CONFIRMATION"
                entry_type = "Confirmation Entry"
                why = "Strong relative activity with acceptable market context."
                next_step = f"Wait for support defense near {fmt_price(support_hi)} or clean break above {fmt_price(breakout)}."
                do_not = "Do not chase vertical move."
                cancel_if = f"Cancel if price loses {fmt_price(invalidation)}."
                focus_bucket = "focus"

            elif final_score >= 5.8 and (strong_momentum or strong_volume):
                action = "Keep On Watch"
                action_short = "EARLY MOMENTUM"
                entry_type = "Early Momentum"
                why = "Momentum is building, but setup is still early and not yet clean enough for higher conviction."
                next_step = f"Watch retest near {fmt_price(support_hi)} or breakout above {fmt_price(breakout)}."
                do_not = "Do not size too big too early."
                cancel_if = f"Cancel if price breaks below {fmt_price(invalidation)}."
                focus_bucket = "emerging"
            else:
                action = "Keep On Watch"
                action_short = "WATCH"
                entry_type = "Watchlist"
                why = "Some potential exists, but the setup is not yet clean enough."
                next_step = f"Wait for either retest nearer {fmt_price(support_hi)} or better breakout behavior above {fmt_price(breakout)}."
                do_not = "Do not rush entry on weak structure."
                cancel_if = f"Cancel if price loses {fmt_price(invalidation)}."
                trap_reason = "not enough clean edge"
                focus_bucket = "emerging"

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
        "supportZone": support_zone,
        "resistanceZone": resistance_zone,
        "buyZone": support_zone,
        "entryAggressive": snr.get("entryAggressive"),
        "entryConfirmation": snr.get("entryConfirmation"),
        "breakoutLevel": breakout,
        "breakoutTrigger": breakout,
        "invalidation": invalidation,
        "tp1": tp1,
        "tp2": tp2,
        "rr": rr,
        "trend": trend,
        "history": snr.get("history", []),
    }
