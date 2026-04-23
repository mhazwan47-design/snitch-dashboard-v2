import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW_FILE = ROOT / "raw-signals.json"
OUTPUT_FILE = ROOT / "signals-input.json"

STABLE_LIKE = {
    "USDC", "USDT", "DAI", "USD", "USDBC", "AXLUSDC",
    "EURC", "FDUSD", "TUSD", "LUSD", "USDE", "SUSDE",
    "AUSD", "USD+", "USD0", "PYUSD", "GUSD", "BUSD", "FRAX", "RLUSD"
}

def is_stable_like(token: str) -> bool:
    t = (token or "").upper().strip()
    if not t:
        return True
    if t in STABLE_LIKE:
        return True
    if "USDC" in t or "USDT" in t:
        return True
    if t.endswith("USD"):
        return True
    return False

def to_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default

def classify_action(score: float, direction: str, risk: str) -> str:
    if direction == "Buy Pressure":
        if score >= 7.0:
            return "WAIT FOR CONFIRMATION"
        if score >= 5.0:
            return "WATCH"
        return "IGNORE"

    if direction == "Sell Pressure":
        if risk == "High" or score >= 5.0:
            return "REDUCE RISK"
        return "WATCH"

    return "IGNORE"

def clean_signal(raw: dict):
    token = str(raw.get("token", "")).strip()
    pair = str(raw.get("pair", "")).strip()
    direction = str(raw.get("direction", "")).strip()
    score = to_float(raw.get("score"))
    impact_pct = to_float(raw.get("impactPct"))
    trade_usd = to_float(raw.get("tradeUsd"))
    risk = str(raw.get("risk", "Medium")).strip()
    confidence = str(raw.get("confidence", "Medium")).strip()

    if not token or not pair:
        return None
    if is_stable_like(token):
        return None
    if trade_usd < 100:
        return None
    if score < 4:
        return None

    action_short = classify_action(score, direction, risk)
    if action_short == "IGNORE":
        return None

    return {
        "token": token,
        "pair": pair,
        "direction": direction,
        "score": round(score, 2),
        "impactPct": round(impact_pct, 2),
        "tradeUsd": trade_usd,
        "risk": risk,
        "confidence": confidence,
        "why": raw.get("why", ""),
        "nextStep": raw.get("nextStep", ""),
        "doNot": raw.get("doNot", ""),
        "cancelIf": raw.get("cancelIf", ""),
        "actionShort": action_short,
    }

def main():
    if not RAW_FILE.exists():
        OUTPUT_FILE.write_text("[]", encoding="utf-8")
        print("raw-signals.json missing")
        return

    raw_data = json.loads(RAW_FILE.read_text(encoding="utf-8"))
    cleaned = []
    seen = set()

    for item in raw_data:
        c = clean_signal(item)
        if not c:
            continue
        key = (c["token"].upper(), c["pair"].upper(), c["direction"])
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(c)

    cleaned.sort(key=lambda x: (x["score"], x["tradeUsd"]), reverse=True)
    OUTPUT_FILE.write_text(json.dumps(cleaned, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
