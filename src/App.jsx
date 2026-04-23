import React, { useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  CartesianGrid,
  Legend,
} from "recharts";
import {
  Search,
  Bell,
  Rocket,
  TrendingUp,
  TriangleAlert,
  Upload,
  RefreshCw,
  Eye,
  Target,
  Filter,
  Activity,
  Gauge,
  Wallet,
  Radar,
  Clock3,
  Link2,
  Database,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";

const starterData = {
  meta: {
    product: "SNITCH Alert Dashboard",
    mode: "Live Monitor",
    marketBias: "Neutral",
    asOf: "Today, 20:45",
    dataSource: "On-chain + exchange-enriched signals",
  },
  metrics: {
    qualifiedSignals: 3,
    tradeFocus: 1,
    emerging: 1,
    caution: 1,
    avgConfidence: 70,
    winRate30d: 58,
  },
  tradeFocusNow: [
    {
      token: "WETH",
      pair: "WETH/USDC",
      action: "Prepare Entry",
      actionShort: "WAIT FOR CONFIRMATION",
      confidence: "Medium",
      score: 7.4,
      direction: "Buy Pressure",
      impactPct: 0.91,
      tradeUsd: 31250,
      risk: "Medium",
      why: "Strong buy pressure on a liquid pair.",
      nextStep: "Open chart now and wait for confirmation.",
      doNot: "Do not chase spike.",
      cancelIf: "Cancel if buy flow fades.",
      history: [
        { d: "Mon", score: 42 },
        { d: "Tue", score: 51 },
        { d: "Wed", score: 57 },
        { d: "Thu", score: 61 },
        { d: "Fri", score: 66 },
        { d: "Sat", score: 71 },
      ],
    },
  ],
  emergingPotential: [
    {
      token: "LINK",
      pair: "LINK/USDC",
      action: "Keep On Watch",
      actionShort: "WATCH",
      confidence: "Medium",
      score: 5.6,
      direction: "Buy Pressure",
      impactPct: 0.31,
      tradeUsd: 4200,
      risk: "Medium",
      why: "Early setup still needs confirmation.",
      nextStep: "Watch next 15–30 minutes.",
      doNot: "Do not enter big size yet.",
      cancelIf: "Cancel if follow-through fails.",
    },
  ],
  cautionAvoid: [
    {
      token: "SOL",
      pair: "SOL/cbBTC",
      action: "Reduce Risk",
      actionShort: "REDUCE RISK",
      confidence: "Medium",
      score: 5.2,
      direction: "Sell Pressure",
      impactPct: 0.97,
      tradeUsd: 2780,
      risk: "High",
      why: "Bearish dominance detected.",
      nextStep: "Avoid fresh entry and reduce bullish bias.",
      doNot: "Do not catch the dip blindly.",
      cancelIf: "Cancel if sell pressure fades.",
    },
  ],
  recentSignals: [
    { time: "Auto", token: "WETH", pair: "WETH/USDC", direction: "Buy Pressure", action: "WAIT FOR CONFIRMATION", score: 7.4, impact: "0.91%", usd: "$31,250.00" },
    { time: "Auto", token: "LINK", pair: "LINK/USDC", direction: "Buy Pressure", action: "WATCH", score: 5.6, impact: "0.31%", usd: "$4,200.00" },
    { time: "Auto", token: "SOL", pair: "SOL/cbBTC", direction: "Sell Pressure", action: "REDUCE RISK", score: 5.2, impact: "0.97%", usd: "$2,780.00" },
  ],
  performance: {
    scoreTrend: [
      { name: "Mon", focus: 4.1, emerging: 3.2, caution: 2.4 },
      { name: "Tue", focus: 4.8, emerging: 3.6, caution: 2.7 },
      { name: "Wed", focus: 5.1, emerging: 3.9, caution: 3.0 },
      { name: "Thu", focus: 5.7, emerging: 4.2, caution: 3.1 },
      { name: "Fri", focus: 6.3, emerging: 4.8, caution: 3.3 },
      { name: "Sat", focus: 7.0, emerging: 5.2, caution: 3.5 },
    ],
    actionMix: [
      { name: "Prepare / Wait", value: 1 },
      { name: "Watch", value: 1 },
      { name: "Avoid / Reduce", value: 1 },
    ],
    proof: [
      { metric: "Qualified Signals", value: "3" },
      { metric: "30D Win Rate", value: "58%" },
      { metric: "Avg Confidence", value: "70/100" },
      { metric: "Risk-Off Alerts", value: "1" },
    ],
  },
};

function normalizeIncomingData(raw) {
  if (!raw || typeof raw !== "object") return starterData;
  return {
    meta: { ...starterData.meta, ...(raw.meta || {}) },
    metrics: { ...starterData.metrics, ...(raw.metrics || {}) },
    tradeFocusNow: Array.isArray(raw.tradeFocusNow) ? raw.tradeFocusNow : [],
    emergingPotential: Array.isArray(raw.emergingPotential) ? raw.emergingPotential : [],
    cautionAvoid: Array.isArray(raw.cautionAvoid) ? raw.cautionAvoid : [],
    recentSignals: Array.isArray(raw.recentSignals) ? raw.recentSignals : [],
    performance: {
      scoreTrend: Array.isArray(raw.performance?.scoreTrend) ? raw.performance.scoreTrend : starterData.performance.scoreTrend,
      actionMix: Array.isArray(raw.performance?.actionMix) ? raw.performance.actionMix : starterData.performance.actionMix,
      proof: Array.isArray(raw.performance?.proof) ? raw.performance.proof : starterData.performance.proof,
    },
  };
}

function fmtUsd(v) {
  if (typeof v !== "number") return v;
  if (Math.abs(v) >= 1_000_000) return `$${(v / 1_000_000).toFixed(2)}M`;
  if (Math.abs(v) >= 1_000) return `$${(v / 1_000).toFixed(2)}K`;
  return `$${v.toFixed(2)}`;
}

function badgeClass(action) {
  const a = (action || "").toUpperCase();
  if (["BUY NOW", "PREPARE ENTRY", "WAIT FOR CONFIRMATION"].includes(a)) return "badge badge-green";
  if (["WATCH", "KEEP ON WATCH"].includes(a)) return "badge badge-amber";
  return "badge badge-red";
}

function riskClass(risk) {
  if (risk === "High") return "badge badge-red";
  if (risk === "Medium") return "badge badge-amber";
  return "badge badge-green";
}

function StatusPill({ status, text }) {
  const extra =
    status === "ok"
      ? "badge-green"
      : status === "warn"
      ? "badge-amber"
      : "badge-slate";
  return <span className={`badge ${extra}`}>{text}</span>;
}

function MiniMetric({ icon: Icon, label, value }) {
  return (
    <div className="mini-metric">
      <div className="mini-metric-label">
        <Icon size={14} />
        <span>{label}</span>
      </div>
      <div className="mini-metric-value">{value}</div>
    </div>
  );
}

function ProgressBar({ value }) {
  const v = Math.max(0, Math.min(100, value));
  return (
    <div className="progress-wrap">
      <div className="progress-bar" style={{ width: `${v}%` }} />
    </div>
  );
}

function TokenCard({ item, onOpen }) {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <div className="token-card">
        <div className="token-head">
          <div>
            <div className="token-name">{item.token}</div>
            <div className="token-pair">{item.pair}</div>
          </div>
          <span className={badgeClass(item.actionShort || item.action)}>{item.actionShort || item.action}</span>
        </div>

        <div className="token-stats">
          <div className="stat-box">
            <div className="stat-label">Score</div>
            <div className="stat-value">{item.score}</div>
          </div>
          <div className="stat-box">
            <div className="stat-label">Risk</div>
            <div className="stat-value">
              <span className={riskClass(item.risk)}>{item.risk}</span>
            </div>
          </div>
        </div>

        <div className="signal-row">
          <span>Signal Strength</span>
          <span>{Math.round(item.score * 10)}/100</span>
        </div>
        <ProgressBar value={Math.round(item.score * 10)} />

        <p className="token-why">{item.why}</p>

        <div className="token-stats">
          <div className="stat-box">
            <div className="stat-label">Trade USD</div>
            <div className="stat-value">{fmtUsd(item.tradeUsd)}</div>
          </div>
          <div className="stat-box">
            <div className="stat-label">Impact</div>
            <div className="stat-value">{item.impactPct}%</div>
          </div>
        </div>

        <div className="btn-row">
          <button className="btn btn-primary" onClick={() => onOpen(item)}>
            <Eye size={16} />
            <span>Open Detail</span>
          </button>
          <button className="btn btn-secondary">
            <Bell size={16} />
            <span>Set Alert</span>
          </button>
        </div>
      </div>
    </motion.div>
  );
}

function DetailPanel({ item }) {
  if (!item) {
    return <div className="panel detail-panel">Select a token card to view the full action plan.</div>;
  }

  return (
    <div className="panel detail-panel">
      <div className="detail-header">
        <div>
          <div className="detail-title">{item.token}</div>
          <div className="detail-sub">{item.pair} · {item.direction}</div>
        </div>
        <div className="detail-badges">
          <span className={badgeClass(item.actionShort || item.action)}>{item.actionShort || item.action}</span>
          <span className={riskClass(item.risk)}>{item.risk}</span>
        </div>
      </div>

      <div className="detail-metrics">
        <MiniMetric icon={Gauge} label="Action Score" value={String(item.score)} />
        <MiniMetric icon={Activity} label="Liquidity Impact" value={`${item.impactPct}%`} />
        <MiniMetric icon={Wallet} label="Trade Value" value={fmtUsd(item.tradeUsd)} />
      </div>

      <div className="detail-grid">
        <div className="detail-box">
          <div className="detail-box-title">Action Now</div>
          <div>{item.action}</div>
        </div>
        <div className="detail-box">
          <div className="detail-box-title">What it means</div>
          <div>{item.why}</div>
        </div>
        <div className="detail-box">
          <div className="detail-box-title">What to do next</div>
          <div>{item.nextStep}</div>
        </div>
        <div className="detail-box">
          <div className="detail-box-title">Do not do</div>
          <div>{item.doNot}</div>
        </div>
        <div className="detail-box">
          <div className="detail-box-title">Cancel plan if</div>
          <div>{item.cancelIf}</div>
        </div>
      </div>

      {Array.isArray(item.history) && item.history.length > 0 && (
        <div className="chart-card">
          <div className="section-title">Recent Performance Matrix</div>
          <div className="section-sub">Signal score trend for this token</div>
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={item.history}>
                <defs>
                  <linearGradient id="scoreGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#22c55e" stopOpacity={0.55} />
                    <stop offset="100%" stopColor="#22c55e" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
                <XAxis dataKey="d" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" />
                <Tooltip contentStyle={{ background: "#020617", border: "1px solid #334155", borderRadius: 16 }} />
                <Area type="monotone" dataKey="score" stroke="#22c55e" fill="url(#scoreGradient)" strokeWidth={3} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}

function Section({ title, desc, items, onOpen }) {
  return (
    <div className="panel">
      <div className="section-title">{title}</div>
      <div className="section-sub">{desc}</div>
      {items.length === 0 ? (
        <div className="empty-text">No clean setup in this section right now.</div>
      ) : (
        <div className="list-grid">
          {items.map((item) => (
            <TokenCard key={`${item.token}-${item.pair}`} item={item} onOpen={onOpen} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function SnitchDashboardApp() {
  const [data, setData] = useState(starterData);
  const [selected, setSelected] = useState(
    starterData.tradeFocusNow[0] ||
    starterData.emergingPotential[0] ||
    starterData.cautionAvoid[0] ||
    null
  );
  const [search, setSearch] = useState("");
  const [minScore, setMinScore] = useState("0");
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [fetchState, setFetchState] = useState("idle");
  const [fetchMessage, setFetchMessage] = useState("Using starter data");
  const [showSourceTools, setShowSourceTools] = useState(false);
  const [dataUrl, setDataUrl] = useState(
    localStorage.getItem("snitch-dashboard-url") || `${import.meta.env.BASE_URL}data/dashboard-current.json`
  );
  const fileRef = useRef(null);

  const loadParsedData = (parsed, sourceLabel = "Loaded data") => {
    const normalized = normalizeIncomingData(parsed);
    setData(normalized);
    setSelected(
      normalized.tradeFocusNow[0] ||
      normalized.emergingPotential[0] ||
      normalized.cautionAvoid[0] ||
      null
    );
    localStorage.setItem("snitch-dashboard-data", JSON.stringify(normalized));
    setFetchMessage(sourceLabel);
  };

  useEffect(() => {
    const saved = localStorage.getItem("snitch-dashboard-data");
    if (saved) {
      try {
        loadParsedData(JSON.parse(saved), "Loaded saved local data");
      } catch {}
    }
  }, []);

  const fetchRemoteData = async () => {
    if (!dataUrl) return;
    try {
      setFetchState("loading");
      const res = await fetch(dataUrl, { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const parsed = await res.json();
      loadParsedData(parsed, `Connected to ${dataUrl}`);
      localStorage.setItem("snitch-dashboard-url", dataUrl);
      setFetchState("ok");
    } catch {
      setFetchState("warn");
      setFetchMessage(`Could not fetch ${dataUrl}`);
    }
  };

  useEffect(() => {
    fetchRemoteData();
  }, []);

  useEffect(() => {
    if (!autoRefresh) return;
    fetchRemoteData();
    const id = setInterval(fetchRemoteData, 30000);
    return () => clearInterval(id);
  }, [autoRefresh, dataUrl]);

  const formatRelativeUpdate = (asOf) => {
    if (!asOf) return "Update time unavailable";
    const parsed = new Date(asOf.replace(" UTC", "Z"));
    if (Number.isNaN(parsed.getTime())) return `Last sync: ${asOf}`;
    const diffMs = Date.now() - parsed.getTime();
    const diffMin = Math.max(0, Math.floor(diffMs / 60000));
    if (diffMin < 1) return "Updated just now";
    if (diffMin === 1) return "Updated 1 min ago";
    if (diffMin < 60) return `Updated ${diffMin} mins ago`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr === 1) return "Updated 1 hour ago";
    return `Updated ${diffHr} hours ago`;
  };

  const allCards = useMemo(() => {
    const merged = [
      ...(data.tradeFocusNow || []),
      ...(data.emergingPotential || []),
      ...(data.cautionAvoid || [])
    ];
    return merged.filter((x) => {
      const scoreOk = Number(x.score || 0) >= Number(minScore || 0);
      const text = `${x.token} ${x.pair} ${x.direction} ${x.action}`.toLowerCase();
      const searchOk = !search || text.includes(search.toLowerCase());
      return scoreOk && searchOk;
    });
  }, [data, search, minScore]);

  const tradeFocusNow = data.tradeFocusNow.filter((x) => allCards.includes(x));
  const emergingPotential = data.emergingPotential.filter((x) => allCards.includes(x));
  const cautionAvoid = data.cautionAvoid.filter((x) => allCards.includes(x));

  const actionMix = data.performance?.actionMix || [];
  const scoreTrend = data.performance?.scoreTrend || [];
  const proof = data.performance?.proof || [];
  const pieColors = ["#22c55e", "#f59e0b", "#ef4444"];

  const loadJson = async (file) => {
    const text = await file.text();
    const parsed = JSON.parse(text);
    loadParsedData(parsed, `Loaded file: ${file.name}`);
    setFetchState("ok");
  };

  return (
    <div className="app-shell">
      <div className="app-container">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="hero-row">
          <div className="panel hero-panel">
            <div className="brand-row">
              <div className="brand-badge">
                <Radar size={24} />
              </div>
              <div>
                <h1 className="hero-title">SNITCH Alert Dashboard</h1>
                <p className="hero-sub">Dark premium signal workspace for fast trading decisions.</p>
              </div>
            </div>
          </div>

          <div className="panel source-panel">
            <div className="source-title">
              <Database size={16} />
              <span>Data Source</span>
            </div>

            <div className="panel" style={{ padding: 16 }}>
              <div style={{ fontWeight: 600, marginBottom: 6 }}>Current status</div>
              <div>{fetchMessage}</div>
            </div>

            <div className="inline-row" style={{ justifyContent: "space-between", flexWrap: "wrap" }}>
              <div className="pills">
                <StatusPill
                  status={fetchState === "ok" ? "ok" : fetchState === "warn" ? "warn" : "idle"}
                  text={fetchState === "ok" ? "Live data" : fetchState === "warn" ? "Fallback data" : "Starter data"}
                />
                <StatusPill
                  status={autoRefresh ? "ok" : "idle"}
                  text={autoRefresh ? "Auto refresh on" : "Manual refresh"}
                />
              </div>

              <button className="btn btn-secondary" onClick={() => setShowSourceTools((v) => !v)}>
                {showSourceTools ? "Hide technical tools" : "Show technical tools"}
              </button>
            </div>

            {showSourceTools && (
              <>
                <div className="source-row">
                  <div className="search-wrap">
                    <Link2 size={16} />
                    <input
                      className="input"
                      value={dataUrl}
                      onChange={(e) => setDataUrl(e.target.value)}
                      placeholder="data/dashboard-current.json"
                    />
                  </div>
                  <button className="btn btn-primary" onClick={fetchRemoteData}>Connect</button>
                </div>

                <div className="btn-row">
                  <button className="btn btn-secondary" onClick={() => setAutoRefresh((v) => !v)}>
                    <RefreshCw size={16} />
                    <span>{autoRefresh ? "Auto Refresh On" : "Auto Refresh Off"}</span>
                  </button>

                  <button className="btn btn-secondary" onClick={() => fileRef.current?.click()}>
                    <Upload size={16} />
                    <span>Load JSON</span>
                  </button>

                  <input
                    ref={fileRef}
                    type="file"
                    accept="application/json"
                    className="hidden-input"
                    onChange={(e) => e.target.files?.[0] && loadJson(e.target.files[0])}
                  />
                </div>
              </>
            )}
          </div>
        </motion.div>

        <div className="panel metrics-panel">
          <div className="metrics-grid">
            <MiniMetric icon={Activity} label="Qualified" value={data.metrics.qualifiedSignals} />
            <MiniMetric icon={Target} label="Focus" value={data.metrics.tradeFocus} />
            <MiniMetric icon={Rocket} label="Emerging" value={data.metrics.emerging} />
            <MiniMetric icon={TriangleAlert} label="Caution" value={data.metrics.caution} />
            <MiniMetric icon={Gauge} label="Avg Confidence" value={`${data.metrics.avgConfidence}%`} />
            <MiniMetric icon={TrendingUp} label="30D Win Rate" value={`${data.metrics.winRate30d}%`} />
          </div>
        </div>

        <div className="panel search-panel">
          <div className="search-wrap">
            <Search size={16} />
            <input
              className="input search-input"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search token, pair, action"
            />
          </div>

          <select className="select" value={minScore} onChange={(e) => setMinScore(e.target.value)}>
            <option value="0">Min score 0</option>
            <option value="4">Min score 4</option>
            <option value="5">Min score 5</option>
            <option value="6">Min score 6</option>
          </select>

          <div className="pills">
            <StatusPill status="ok" text={formatRelativeUpdate(data.meta.asOf)} />
            <StatusPill status="ok" text={data.meta.marketBias} />
          </div>
        </div>

        <div className="main-grid">
          <div className="stack-grid">
            <Section
              title="Trade Focus Now"
              desc="Highest priority names to monitor immediately."
              items={tradeFocusNow}
              onOpen={setSelected}
            />
            <Section
              title="Emerging Potential"
              desc="Early setups that still need confirmation."
              items={emergingPotential}
              onOpen={setSelected}
            />
            <Section
              title="Caution / Avoid"
              desc="Risky or bearish structures that need caution."
              items={cautionAvoid}
              onOpen={setSelected}
            />
          </div>

          <DetailPanel item={selected} />
        </div>

        <div className="charts-grid">
          <div className="panel">
            <div className="section-title">Action Mix</div>
            <div className="section-sub">Distribution of current dashboard actions</div>
            <div className="chart-wrap">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={actionMix} dataKey="value" nameKey="name" innerRadius={60} outerRadius={95} paddingAngle={3}>
                    {actionMix.map((entry, index) => (
                      <Cell key={entry.name} fill={pieColors[index % pieColors.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ background: "#020617", border: "1px solid #334155", borderRadius: 16 }} />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="panel">
            <div className="section-title">Performance Matrix</div>
            <div className="section-sub">Focus, emerging, and caution trend over recent sessions</div>
            <div className="chart-wrap">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={scoreTrend}>
                  <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
                  <XAxis dataKey="name" stroke="#94a3b8" />
                  <YAxis stroke="#94a3b8" />
                  <Tooltip contentStyle={{ background: "#020617", border: "1px solid #334155", borderRadius: 16 }} />
                  <Legend />
                  <Bar dataKey="focus" fill="#22c55e" radius={[8, 8, 0, 0]} />
                  <Bar dataKey="emerging" fill="#f59e0b" radius={[8, 8, 0, 0]} />
                  <Bar dataKey="caution" fill="#ef4444" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        <div className="bottom-grid">
          <div className="panel">
            <div className="section-title">Proof Snapshot</div>
            <div className="section-sub">Quick performance metrics</div>
            <div className="proof-grid">
              {proof.map((p) => (
                <div key={p.metric} className="proof-box">
                  <div className="proof-label">{p.metric}</div>
                  <div className="proof-value">{p.value}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="panel">
            <div className="section-title">Recent Qualified Signals</div>
            <div className="section-sub">Latest filtered signals worth attention</div>
            <div className="recent-list">
              {(data.recentSignals || []).map((r) => (
                <button
                  key={`${r.time}-${r.token}`}
                  className="recent-item"
                  onClick={() => {
                    const found = [...data.tradeFocusNow, ...data.emergingPotential, ...data.cautionAvoid].find((x) => x.token === r.token);
                    if (found) setSelected(found);
                  }}
                >
                  <div className="recent-top">
                    <div>
                      <div className="recent-token">{r.token} <span>{r.pair}</span></div>
                      <div className="recent-dir">{r.direction}</div>
                    </div>
                    <div className="recent-right">
                      <span className={badgeClass(r.action)}>{r.action}</span>
                      <div className="recent-time">{r.time}</div>
                    </div>
                  </div>
                  <div className="recent-metrics">
                    <div>Score <strong>{r.score}</strong></div>
                    <div>Impact <strong>{r.impact}</strong></div>
                    <div>USD <strong>{r.usd}</strong></div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
