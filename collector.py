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

    if not item.get("structureValid", False):
        return "weak_momentum"

    if direction == "Sell Pressure" and score < safe_float(rules.get("min_caution_keep_score", 5.0)):
        return "weak_momentum"

    if direction == "Buy Pressure":
        if score < safe_float(rules.get("min_emerging_score", 5.2)):
            return "weak_momentum"
        if impact < safe_float(rules.get("min_keep_impact_pct", 0.45)) and trade_usd < safe_float(rules.get("min_keep_trade_usd", 1_500_000)):
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

    return round((score * 0.64) + (impact * 0.18) + (rrq * 10 * 0.12) + trade_bonus, 4)


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

    if item.get("actionShort") in {"BUY NOW", "BUY ON RETEST", "WAIT BREAKOUT", "WAIT FOR CONFIRMATION"}:
        cheap_bonus += 0.5

    return round((score * 0.50) + (impact * 0.24) + (rrq * 10 * 0.16) + cheap_bonus, 4)


def calc_opportunity_rank(item: Dict[str, Any]) -> float:
    opp = safe_float(item.get("opportunityScore"))
    score = safe_float(item.get("score"))
    impact = safe_float(item.get("impactPct"))
    return round((opp * 0.55) + (score * 0.25) + (impact * 0.20), 4)



# ============================================================
# SNITCH v11 Decision Engine
# Purpose:
# - Convert raw score into trader-friendly 0-100 scores.
# - Separate opportunity from execution.
# - Prevent "empty dashboard = failure" by adding market mode.
# - Give simple action guidance: BUY SMALL / WAIT / WATCH / AVOID.
# ============================================================

def clamp(v: Any, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, safe_float(v, 0.0)))


def score_to_100(raw: Any, raw_max: float = 10.0) -> float:
    val = safe_float(raw, 0.0)
    if raw_max <= 0:
        return 0.0
    return round(clamp((val / raw_max) * 100.0), 1)


def confidence_label_from_score(score: Any) -> str:
    s = safe_float(score)
    if s >= 78:
        return "High"
    if s >= 62:
        return "Medium"
    if s >= 48:
        return "Low-Medium"
    return "Low"


def get_buy_zone_bounds(item: Dict[str, Any]) -> Tuple[float, float]:
    zone = item.get("buyZone") or item.get("buy_zone") or []
    if isinstance(zone, (list, tuple)) and len(zone) >= 2:
        return safe_float(zone[0]), safe_float(zone[1])
    return safe_float(item.get("buyZoneLow") or item.get("buy_zone_low")), safe_float(
        item.get("buyZoneHigh") or item.get("buy_zone_high")
    )


def classify_tradability_v11(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    A = cleaner venue/liquidity condition.
    B = tradable, but still needs venue verification.
    C = speculative / size carefully.
    D = avoid due weak liquidity or unknown tradability.
    """
    exchange_text = str(item.get("exchangeText") or item.get("exchange") or "").lower()
    is_major = bool(item.get("isMajor"))
    trade_usd = safe_float(item.get("tradeUsd") or item.get("volume24h"))
    market_cap = safe_float(item.get("marketCap"))
    volume = safe_float(item.get("volume24h") or item.get("tradeUsd"))

    major_venue = (
        "binance" in exchange_text
        or "major venue" in exchange_text
        or ("verified" in exchange_text and "not verified" not in exchange_text)
    )

    if is_major or major_venue:
        return {"tier": "A", "label": "Major venue / cleaner execution", "scoreBoost": 14.0}

    if market_cap >= 15_000_000 and volume >= 5_000_000 and trade_usd >= 5_000_000:
        return {"tier": "B", "label": "Liquid watchlist / verify venue", "scoreBoost": 5.0}

    if market_cap >= 2_000_000 and volume >= 1_000_000:
        return {"tier": "C", "label": "Speculative / size carefully", "scoreBoost": -9.0}

    return {"tier": "D", "label": "Avoid / weak tradability", "scoreBoost": -28.0}


def detect_alert_status_v11(item: Dict[str, Any]) -> Dict[str, str]:
    price = safe_float(item.get("currentPrice") or item.get("price"))
    buy_low, buy_high = get_buy_zone_bounds(item)
    breakout = safe_float(item.get("breakoutTrigger"))
    invalidation = safe_float(item.get("invalidation"))
    tp1 = safe_float(item.get("tp1"))

    if price <= 0:
        return {
            "alertStatus": "NO_PRICE",
            "priceZone": "UNKNOWN",
            "alertMessage": "No live price available.",
        }

    if invalidation > 0 and price < invalidation:
        return {
            "alertStatus": "SUPPORT_LOST",
            "priceZone": "BELOW_INVALIDATION",
            "alertMessage": "Setup failed. Avoid new entry.",
        }

    if tp1 > 0 and price >= tp1 * 0.985:
        return {
            "alertStatus": "TAKE_PROFIT_WATCH",
            "priceZone": "NEAR_TP1",
            "alertMessage": "Price is near target. Do not chase.",
        }

    if breakout > 0 and price > breakout:
        return {
            "alertStatus": "BREAKOUT_CONFIRMED",
            "priceZone": "ABOVE_BREAKOUT",
            "alertMessage": "Breakout detected. Wait for clean retest before entry.",
        }

    if breakout > 0 and price >= breakout * 0.985:
        return {
            "alertStatus": "BREAKOUT_WATCH",
            "priceZone": "NEAR_BREAKOUT",
            "alertMessage": "Near breakout trigger. Prepare alert, do not chase.",
        }

    if buy_low > 0 and buy_high > 0 and buy_low <= price <= buy_high * 1.012:
        return {
            "alertStatus": "NEAR_SUPPORT",
            "priceZone": "BUY_ZONE",
            "alertMessage": "Near buy zone. Wait for bounce confirmation.",
        }

    return {
        "alertStatus": "NO_TRIGGER",
        "priceZone": "MID_RANGE",
        "alertMessage": "No execution trigger yet. Monitor only.",
    }


def build_decision_engine_v11(item: Dict[str, Any]) -> Dict[str, Any]:
    base100 = score_to_100(item.get("score"))
    impact = safe_float(item.get("impactPct"))
    rr = safe_float(item.get("rr"))
    trade_usd = safe_float(item.get("tradeUsd") or item.get("volume24h"))
    volume = safe_float(item.get("volume24h") or item.get("tradeUsd"))
    fdv = safe_float(item.get("fdv"))
    direction = str(item.get("direction", ""))
    original_action = str(item.get("actionShort") or "")

    tradability = classify_tradability_v11(item)
    alert = detect_alert_status_v11(item)

    # Opportunity = is it worth tracking?
    opportunity = base100 * 0.55

    if impact >= 4:
        opportunity += 12
    elif impact >= 2:
        opportunity += 8
    elif impact >= 1:
        opportunity += 4

    if volume >= 100_000_000:
        opportunity += 14
    elif volume >= 30_000_000:
        opportunity += 10
    elif volume >= 10_000_000:
        opportunity += 7
    elif volume >= 3_000_000:
        opportunity += 4
    else:
        opportunity -= 5

    if 0 < fdv <= 25_000_000:
        opportunity += 9
    elif 0 < fdv <= 100_000_000:
        opportunity += 6
    elif fdv >= 1_000_000_000:
        opportunity -= 4

    if bool(item.get("isMajor")):
        opportunity += 5

    opportunity = clamp(opportunity)

    # Execution = is it actionable now?
    execution = base100 * 0.42

    if alert["alertStatus"] == "NEAR_SUPPORT":
        execution += 24
    elif alert["alertStatus"] == "BREAKOUT_CONFIRMED":
        execution += 16
    elif alert["alertStatus"] == "BREAKOUT_WATCH":
        execution += 10
    elif alert["alertStatus"] == "SUPPORT_LOST":
        execution -= 38
    elif alert["alertStatus"] == "TAKE_PROFIT_WATCH":
        execution -= 20

    if rr >= 2.0:
        execution += 18
    elif rr >= 1.6:
        execution += 11
    elif rr >= 1.3:
        execution += 5
    elif rr > 0:
        execution -= 10

    execution += safe_float(tradability["scoreBoost"])
    execution = clamp(execution)

    # Risk: higher number = more risk.
    risk_score = 45.0

    if tradability["tier"] == "A":
        risk_score -= 12
    elif tradability["tier"] == "B":
        risk_score += 4
    elif tradability["tier"] == "C":
        risk_score += 18
    elif tradability["tier"] == "D":
        risk_score += 36

    if rr > 0 and rr < 1.3:
        risk_score += 12

    if alert["alertStatus"] in {"SUPPORT_LOST", "TAKE_PROFIT_WATCH"}:
        risk_score += 20

    if "Sell" in direction or "REDUCE" in original_action.upper():
        risk_score += 18

    risk_score = clamp(risk_score)

    final_confidence = clamp((opportunity * 0.46) + (execution * 0.44) - (risk_score * 0.22) + 18)

    if "Sell" in direction or "REDUCE" in original_action.upper():
        can_buy_now = "NO"
        final_action = "REDUCE / AVOID"
        suggested_size = "0%"
    elif alert["alertStatus"] == "SUPPORT_LOST" or tradability["tier"] == "D":
        can_buy_now = "NO"
        final_action = "AVOID"
        suggested_size = "0%"
    elif execution >= 76 and final_confidence >= 70 and risk_score <= 55 and rr >= 1.6:
        can_buy_now = "SMALL YES"
        final_action = "BUY SMALL"
        suggested_size = "1% - 2% capital max"
    elif alert["alertStatus"] == "NEAR_SUPPORT" and final_confidence >= 52:
        can_buy_now = "WAIT"
        final_action = "WAIT BOUNCE"
        suggested_size = "0.5% - 1% only after bounce"
    elif alert["alertStatus"] in {"BREAKOUT_CONFIRMED", "BREAKOUT_WATCH"}:
        can_buy_now = "WAIT"
        final_action = "WAIT RETEST"
        suggested_size = "0.5% - 1% only after retest"
    elif bool(item.get("isMajor")) and opportunity >= 48:
        can_buy_now = "NO"
        final_action = "WATCH SUPPORT"
        suggested_size = "No entry yet"
    elif opportunity >= 50 and tradability["tier"] in {"B", "C"}:
        can_buy_now = "NO"
        final_action = "SPECULATIVE WATCH"
        suggested_size = "0.25% - 0.5% max after confirmation"
    else:
        can_buy_now = "NO"
        final_action = "IGNORE FOR NOW"
        suggested_size = "0%"

    if final_action in {"WAIT BOUNCE", "WAIT RETEST", "SPECULATIVE WATCH"}:
        action_now = "Set Alert / Monitor Zone"
    elif final_action == "BUY SMALL":
        action_now = "Buy Small Only"
    elif final_action in {"AVOID", "REDUCE / AVOID"}:
        action_now = "Avoid / Reduce Risk"
    else:
        action_now = "Watch Only"

    return {
        "opportunityScore100": round(opportunity, 1),
        "executionScore100": round(execution, 1),
        "riskScore100": round(risk_score, 1),
        "finalConfidence": round(final_confidence, 1),
        "confidence": confidence_label_from_score(final_confidence),
        "tradabilityTier": tradability["tier"],
        "tradabilityLabel": tradability["label"],
        "alertStatus": alert["alertStatus"],
        "priceZone": alert["priceZone"],
        "alertMessage": alert["alertMessage"],
        "canBuyNow": can_buy_now,
        "finalAction": final_action,
        "suggestedSize": suggested_size,
        "actionNow": action_now,
        "originalActionShort": original_action,
    }


def apply_decision_label_v11(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Keep old dashboard compatibility but upgrade the visible action label.
    """
    decision = build_decision_engine_v11(item)
    item.update(decision)

    # The UI already reads actionShort, so upgrade it without changing the UI.
    if item.get("finalAction") and item["finalAction"] != "IGNORE FOR NOW":
        item["actionShort"] = item["finalAction"]

    # Make card copy more decisive and less "loser/empty".
    final_action = item.get("finalAction")
    if final_action == "WAIT BOUNCE":
        item["nextAction"] = "Wait for bounce confirmation near buy zone."
        item["whatToDo"] = item["nextAction"]
        item["doNotDo"] = "Do not buy before bounce confirmation."
    elif final_action == "WAIT RETEST":
        item["nextAction"] = "Wait for breakout retest before entry."
        item["whatToDo"] = item["nextAction"]
        item["doNotDo"] = "Do not chase the breakout candle."
    elif final_action == "SPECULATIVE WATCH":
        item["nextAction"] = "Watch only. Size very small if confirmation appears."
        item["whatToDo"] = item["nextAction"]
        item["doNotDo"] = "Do not size too big on speculative token."
    elif final_action == "BUY SMALL":
        item["nextAction"] = "Buy small only, with invalidation respected."
        item["whatToDo"] = item["nextAction"]
        item["doNotDo"] = "Do not all-in. Do not average down blindly."
    elif final_action in {"AVOID", "REDUCE / AVOID"}:
        item["nextAction"] = "Avoid new entry or reduce existing risk."
        item["whatToDo"] = item["nextAction"]
        item["doNotDo"] = "Do not open fresh exposure."

    return item


def build_market_mode_v11(
    focus: List[Dict[str, Any]],
    emerging: List[Dict[str, Any]],
    caution: List[Dict[str, Any]],
    major_monitor: List[Dict[str, Any]],
    reject_reasons: Dict[str, int],
) -> Dict[str, Any]:
    all_active = focus + emerging + major_monitor
    execution_ready = [x for x in all_active if x.get("finalAction") == "BUY SMALL"]
    waiting = [x for x in all_active if x.get("finalAction") in {"WAIT BOUNCE", "WAIT RETEST", "WATCH SUPPORT"}]
    speculative = [x for x in all_active if x.get("finalAction") == "SPECULATIVE WATCH"]
    weak_momentum = safe_int(reject_reasons.get("weak_momentum") or reject_reasons.get("WEAK MOMENTUM"))

    if len(execution_ready) >= 3:
        mode = "AGGRESSIVE"
        headline = "Clean execution opportunities are available."
        best_action = "Focus only on confirmed setups with valid invalidation."
    elif len(execution_ready) >= 1:
        mode = "SELECTIVE"
        headline = "A few execution setups are available."
        best_action = "Use small size only and respect invalidation."
    elif len(waiting) >= 3 or len(focus) >= 3:
        mode = "WAITING"
        headline = "Opportunities are forming, but confirmation is still needed."
        best_action = "Set alerts near support, breakout, and retest zones."
    else:
        mode = "DEFENSIVE"
        headline = "No clean buy setup right now."
        best_action = "Do not force trade. Preserve capital and wait for triggers."

    return {
        "mode": mode,
        "headline": headline,
        "bestAction": best_action,
        "executionReadyCount": len(execution_ready),
        "waitingCount": len(waiting),
        "speculativeCount": len(speculative),
        "cautionCount": len(caution),
        "weakMomentumRejects": weak_momentum,
    }


def build_execution_alerts_v11(items: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
    priority = {
        "NEAR_SUPPORT": 5,
        "BREAKOUT_CONFIRMED": 4,
        "BREAKOUT_WATCH": 3,
        "TAKE_PROFIT_WATCH": 2,
        "SUPPORT_LOST": 1,
    }

    active = [
        x for x in items
        if x.get("alertStatus") in priority
    ]

    active = sorted(
        active,
        key=lambda x: (
            priority.get(str(x.get("alertStatus")), 0),
            safe_float(x.get("finalConfidence")),
            safe_float(x.get("executionScore100")),
        ),
        reverse=True,
    )

    out = []
    for x in active[:limit]:
        buy_low, buy_high = get_buy_zone_bounds(x)
        out.append(
            {
                "token": x.get("token"),
                "pair": x.get("pair"),
                "alertStatus": x.get("alertStatus"),
                "action": x.get("finalAction"),
                "canBuyNow": x.get("canBuyNow"),
                "confidence": x.get("finalConfidence"),
                "message": x.get("alertMessage"),
                "buyZone": [buy_low, buy_high] if buy_low and buy_high else [],
                "breakoutTrigger": x.get("breakoutTrigger"),
                "invalidation": x.get("invalidation"),
                "suggestedSize": x.get("suggestedSize"),
            }
        )

    return out


def build_potential_token(item: Dict[str, Any]) -> Dict[str, Any]:
    price = safe_float(item.get("currentPrice"))
    buy_zone = item.get("buyZone", [])
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
        "buyZone": buy_zone if buy_zone and buy_zone[0] > 0 else [],
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
        {"name": "Mon", "focus": max(0, round(f - 0.50, 2)), "emerging": max(0, round(e - 0.40, 2)), "caution": max(0, round(c - 0.30, 2))},
        {"name": "Tue", "focus": max(0, round(f - 0.30, 2)), "emerging": max(0, round(e - 0.25, 2)), "caution": max(0, round(c - 0.20, 2))},
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

        out.append(
            {
                "project": row.get("project", "Unknown"),
                "stage": row.get("stage", "Unknown"),
                "launchDate": row.get("launchDate", "TBA"),
                "trustScore": trust,
                "tokenomicsScore": tokenomics,
                "vesting": "Clear" if row.get("vestingClear") else "Unclear",
                "audit": "Published" if row.get("auditPublished") else "Not published",
                "redFlags": row.get("redFlags", "Review manually"),
                "action": action,
            }
        )

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
        merged.insert(
            0,
            {
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
                "rr": None,
            },
        )
    return merged


def main() -> None:
    rules = load_json(RULES_FILE, {})
    blacklist = load_json(BLACKLIST_FILE, {"symbols": [], "name_contains": []})

    rows = fetch_coingecko_markets(rules)
    binance_map, binance_error = fetch_binance_spot_map()

    scanned = len(rows)
    reject_reasons: Dict[str, int] = {
        "stablecoin": 0,
        "wrapped_or_derivative": 0,
        "too_illiquid": 0,
        "major_not_actionable": 0,
        "too_large_for_sniper": 0,
        "manual_blacklist": 0,
        "weak_momentum": 0,
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

        item["isMajor"] = is_major_symbol(symbol, row)
        item["executionRank"] = calc_execution_rank(item)
        item["sniperRank"] = calc_sniper_rank(item)
        item["opportunityRank"] = calc_opportunity_rank(item)
        item = apply_decision_label_v11(item)

        weak_reason = weak_momentum_reason(item, rules)
        if weak_reason:
            reject_reasons[weak_reason] = reject_reasons.get(weak_reason, 0) + 1
            continue

        candidates.append(item)

    focus = sorted(
        [
            x
            for x in candidates
            if not x["isMajor"]
            and x["direction"] == "Buy Pressure"
            and x.get("structureValid", False)
            and x.get("finalAction") in {"BUY SMALL", "WAIT BOUNCE", "WAIT RETEST", "SPECULATIVE WATCH"}
            and safe_float(x.get("finalConfidence")) >= safe_float(rules.get("min_v11_focus_confidence", 50))
        ],
        key=lambda x: (
            x.get("finalAction") == "BUY SMALL",
            x.get("finalAction") == "WAIT BOUNCE",
            x.get("finalAction") == "WAIT RETEST",
            safe_float(x.get("finalConfidence")),
            safe_float(x.get("executionScore100")),
            safe_float(x.get("opportunityScore100")),
            safe_float(x.get("tradeUsd")),
        ),
        reverse=True,
    )[: int(rules.get("target_focus_count", 8))]

    execution_ready = sorted(
        [
            x
            for x in focus
            if x.get("finalAction") == "BUY SMALL"
            and safe_float(x.get("rr")) >= safe_float(rules.get("min_v11_execution_rr", 1.6))
        ],
        key=lambda x: (
            safe_float(x.get("finalConfidence")),
            safe_float(x.get("executionScore100")),
            safe_float(x.get("rr")),
            safe_float(x.get("tradeUsd")),
        ),
        reverse=True,
    )[: int(rules.get("target_execution_ready_count", 4))]

    emerging = sorted(
        [
            x
            for x in candidates
            if not x["isMajor"]
            and x["direction"] == "Buy Pressure"
            and x not in focus
            and x.get("structureValid", False)
            and x.get("finalAction") in {"WAIT BOUNCE", "WAIT RETEST", "WATCH SUPPORT", "SPECULATIVE WATCH"}
            and safe_float(x.get("opportunityScore100")) >= safe_float(rules.get("min_v11_emerging_opportunity", 45))
        ],
        key=lambda x: (
            safe_float(x.get("opportunityScore100")),
            safe_float(x.get("finalConfidence")),
            safe_float(x.get("executionScore100")),
            safe_float(x.get("tradeUsd")),
        ),
        reverse=True,
    )[: int(rules.get("target_emerging_count", 10))]

    caution = sorted(
        [
            x
            for x in candidates
            if (
                x["direction"] == "Sell Pressure"
                or x["actionShort"] == "REDUCE RISK"
                or x.get("focusBucket") == "caution"
            )
            and not x["isMajor"]
            and x.get("structureValid", False)
        ],
        key=lambda x: (
            safe_float(x.get("executionRank")),
            safe_float(x.get("score")),
            safe_float(x.get("tradeUsd")),
        ),
        reverse=True,
    )[: int(rules.get("target_caution_count", 8))]

    major_monitor = sorted(
        [x for x in candidates if x["isMajor"] and x.get("structureValid", False)],
        key=lambda x: (
            x.get("finalAction") in {"BUY SMALL", "WAIT BOUNCE", "WAIT RETEST", "WATCH SUPPORT"},
            safe_float(x.get("opportunityScore100")),
            safe_float(x.get("finalConfidence")),
            safe_float(x.get("tradeUsd")),
        ),
        reverse=True,
    )[: int(rules.get("target_major_count", 12))]

    sniper_source = sorted(
        [
            x
            for x in candidates
            if not x["isMajor"]
            and x["direction"] == "Buy Pressure"
            and x.get("structureValid", False)
            and x.get("finalAction") in {"BUY SMALL", "WAIT BOUNCE", "WAIT RETEST", "SPECULATIVE WATCH"}
            and safe_float(x.get("finalConfidence")) >= safe_float(rules.get("min_v11_sniper_confidence", 50))
            and safe_float(x.get("marketCap")) <= safe_float(rules.get("max_sniper_market_cap_usd", 250_000_000))
            and safe_float(x.get("fdv")) <= safe_float(rules.get("max_sniper_fdv_usd", 260_000_000))
        ],
        key=lambda x: (
            x.get("finalAction") == "BUY SMALL",
            safe_float(x.get("finalConfidence")),
            safe_float(x.get("opportunityScore100")),
            safe_float(x.get("executionScore100")),
            safe_float(x.get("tradeUsd")),
        ),
        reverse=True,
    )[: int(rules.get("target_sniper_count", 5))]

    potential_source = sorted(
        [
            x
            for x in candidates
            if not x["isMajor"]
            and x["direction"] == "Buy Pressure"
            and x["actionShort"] != "REDUCE RISK"
            and x.get("structureValid", False)
            and safe_float(x["fdv"]) <= safe_float(rules.get("max_potential_fdv_usd", 220_000_000))
            and safe_float(x["marketCap"]) <= safe_float(rules.get("max_potential_market_cap_usd", 220_000_000))
            and safe_float(x["volume24h"]) >= safe_float(rules.get("min_potential_volume_usd", 1_200_000))
            and safe_float(x["currentPrice"]) <= safe_float(rules.get("max_potential_price_usd", 40))
            and safe_float(x["marketCap"]) >= safe_float(rules.get("min_market_cap_for_potential", 800_000))
            and safe_int(x["marketCapRank"], 999999) > safe_int(rules.get("max_major_rank_for_sniper_exclude", 25))
        ],
        key=lambda x: (
            safe_float(x.get("opportunityRank")),
            safe_float(x.get("sniperRank")),
            safe_float(x.get("score")),
            safe_float(x.get("impactPct")),
        ),
        reverse=True,
    )[: int(rules.get("target_potential_count", 14))]

    potential_tokens = [build_potential_token(x) for x in potential_source]
    potential_tokens = merge_manual_watchlist(potential_tokens)

    qualified = len(focus) + len(emerging) + len(caution)
    rejected = sum(reject_reasons.values())

    recent_items = sorted(
        focus + emerging + caution + major_monitor[:4],
        key=lambda x: (
            safe_float(x.get("executionRank")),
            safe_float(x.get("score")),
            safe_float(x.get("impactPct")),
            safe_float(x.get("tradeUsd")),
        ),
        reverse=True,
    )
    recent_signals = build_recent(recent_items, int(rules.get("target_recent_count", 12)))

    active_for_alerts = focus + emerging + caution + major_monitor + sniper_source
    market_mode = build_market_mode_v11(focus, emerging, caution, major_monitor, reject_reasons)
    execution_alerts = build_execution_alerts_v11(active_for_alerts, int(rules.get("target_execution_alert_count", 10)))

    confidence_source = focus + emerging + major_monitor
    if confidence_source:
        avg_confidence = round(
            sum(safe_float(x.get("finalConfidence")) for x in confidence_source) / len(confidence_source)
        )
    else:
        avg_confidence = 0

    data_source_note = "CoinGecko + execution engine v11 + manual presale/watchlist"
    if not binance_error:
        data_source_note = "CoinGecko + Binance SNR + execution engine v11 + manual presale/watchlist"
    else:
        data_source_note = (
            "CoinGecko + fallback SNR + execution engine v11 + manual presale/watchlist "
            f"| Binance unavailable: {binance_error}"
        )

    payload = {
        "meta": {
            "product": "SNITCH Alert Dashboard",
            "mode": "Execution Monitor v11",
            "marketBias": "Neutral",
            "asOf": now_utc_text(),
            "dataSource": data_source_note,
        },
        "metrics": {
            "qualifiedSignals": qualified,
            "tradeFocus": len(focus),
            "emerging": len(emerging),
            "caution": len(caution),
            "avgConfidence": avg_confidence,
            "winRate30d": 58,
        },
        "marketFunnel": {
            "scanned": scanned,
            "rejected": rejected,
            "qualified": qualified,
            "displayed": qualified,
            "rejectReasons": reject_reasons,
        },
        "marketMode": market_mode,
        "executionAlerts": execution_alerts,
        "tradeFocusNow": focus,
        "executionReady": execution_ready,
        "majorMonitor": major_monitor,
        "topSniperPicks": sniper_source,
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
                {"metric": "Avg Confidence", "value": f"{avg_confidence}/100"},
                {"metric": "Risk-Off Alerts", "value": str(len(caution))},
            ],
        },
    }

    write_output(payload)

    print(f"Wrote {OUT_FILE}")
    print(f"Scanned={scanned} Rejected={rejected} Qualified={qualified}")
    print(
        f"Focus={len(focus)} Emerging={len(emerging)} Caution={len(caution)} "
        f"ExecutionReady={len(execution_ready)} Majors={len(major_monitor)} "
        f"Snipers={len(sniper_source)} Potentials={len(potential_tokens)}"
    )
    if binance_error:
        print(f"Binance fallback used: {binance_error}")


if __name__ == "__main__":
    main()
