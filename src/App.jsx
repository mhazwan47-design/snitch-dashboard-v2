import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Database,
  Eye,
  Filter,
  LineChart,
  Radar,
  Rocket,
  Search,
  ShieldAlert,
  Signal,
  Target,
  TrendingUp,
  Wallet,
  Zap,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Badge } from "./components/ui/badge";
import { Button } from "./components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./components/ui/card";
import { Input } from "./components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "./components/ui/tabs";

const DEFAULT_DATA_URL = "/snitch-dashboard-v2/data/dashboard-current.json";

const emptyDashboard = {
  meta: {
    product: "SNITCH Alert Dashboard",
    mode: "Execution Monitor",
    marketBias: "Neutral",
    asOf: "No data",
    dataSource: "No source",
  },
  metrics: {
    qualifiedSignals: 0,
    tradeFocus: 0,
    emerging: 0,
    caution: 0,
    avgConfidence: 0,
    winRate30d: 0,
  },
  marketFunnel: {
    scanned: 0,
    rejected: 0,
    qualified: 0,
    displayed: 0,
    rejectReasons: {},
  },
  tradeFocusNow: [],
  executionReady: [],
  majorMonitor: [],
  topSniperPicks: [],
  emergingPotential: [],
  cautionAvoid: [],
  potentialTokens: [],
  presaleWatchlist: [],
  recentSignals: [],
  performance: {
    scoreTrend: [],
    actionMix: [],
    proof: [],
  },
};

function cn(...classes) {
  return classes.filter(Boolean).join(" ");
}

function safeArray(v) {
  return Array.isArray(v) ? v : [];
}

function toNumber(v, fallback = 0) {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

function fmtCompactUsd(value) {
  const num = toNumber(value, NaN);
  if (!Number.isFinite(num)) return "N/A";
  if (Math.abs(num) >= 1_000_000_000) return `$${(num / 1_000_000_000).toFixed(2)}B`;
  if (Math.abs(num) >= 1_000_000) return `$${(num / 1_000_000).toFixed(2)}M`;
  if (Math.abs(num) >= 1_000) return `$${(num / 1_000).toFixed(2)}K`;
  return `$${num.toFixed(2)}`;
}

function fmtPlain(value) {
  const num = toNumber(value, NaN);
  if (!Number.isFinite(num)) return "N/A";
  if (Math.abs(num) >= 1000) return num.toLocaleString(undefined, { maximumFractionDigits: 2 });
  if (Math.abs(num) >= 1) return num.toFixed(4);
  return num.toPrecision(4);
}

function fmtPercent(value) {
  const num = toNumber(value, NaN);
  if (!Number.isFinite(num)) return "N/A";
  return `${num.toFixed(2)}%`;
}

function fmtRR(value) {
  const num = toNumber(value, NaN);
  if (!Number.isFinite(num) || num <= 0) return "N/A";
  return `1:${num.toFixed(2)}`;
}

function fmtPrice(value) {
  const num = toNumber(value, NaN);
  if (!Number.isFinite(num)) return "N/A";
  if (Math.abs(num) >= 1000) return num.toLocaleString(undefined, { maximumFractionDigits: 2 });
  if (Math.abs(num) >= 1) {
    return num.toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 4,
    });
  }
  return num.toPrecision(5);
}

function fmtZone(zone) {
  if (!Array.isArray(zone) || zone.length < 2) return "N/A";
  return `${fmtPrice(zone[0])} – ${fmtPrice(zone[1])}`;
}

function scoreTone(score) {
  const n = toNumber(score);
  if (n >= 8.5) return "text-emerald-400";
  if (n >= 7) return "text-teal-300";
  if (n >= 5.8) return "text-amber-300";
  return "text-rose-300";
}

function badgeClass(action) {
  const a = String(action || "").toUpperCase();
  if (
    a.includes("BUY") ||
    a.includes("CONFIRMATION") ||
    a.includes("BREAKOUT")
  ) {
    return "border-emerald-500/40 bg-emerald-500/10 text-emerald-300";
  }
  if (
    a.includes("WATCH") ||
    a.includes("MOMENTUM") ||
    a.includes("RETEST")
  ) {
    return "border-amber-500/40 bg-amber-500/10 text-amber-300";
  }
  if (a.includes("RISK") || a.includes("REDUCE")) {
    return "border-rose-500/40 bg-rose-500/10 text-rose-300";
  }
  if (a.includes("MAJOR")) {
    return "border-cyan-500/40 bg-cyan-500/10 text-cyan-300";
  }
  return "border-slate-600 bg-slate-800/70 text-slate-200";
}

function riskTextClass(risk) {
  const r = String(risk || "").toLowerCase();
  if (r === "low") return "text-emerald-300";
  if (r === "medium") return "text-amber-300";
  return "text-rose-300";
}

function riskBadgeClass(risk) {
  const r = String(risk || "").toLowerCase();
  if (r === "low") return "border-emerald-500/40 bg-emerald-500/10 text-emerald-300";
  if (r === "medium") return "border-amber-500/40 bg-amber-500/10 text-amber-300";
  return "border-rose-500/40 bg-rose-500/10 text-rose-300";
}

function GaugeIcon() {
  return <Radar className="h-4 w-4" />;
}

function useDashboardData() {
  const [dashboard, setDashboard] = useState(emptyDashboard);
  const [dataUrl, setDataUrl] = useState(localStorage.getItem("snitch-dashboard-url") || DEFAULT_DATA_URL);
  const [loading, setLoading] = useState(false);
  const [fetchMessage, setFetchMessage] = useState("Using live dashboard source");
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [technicalOpen, setTechnicalOpen] = useState(false);

  const fetchDashboard = async (targetUrl = dataUrl) => {
    setLoading(true);
    try {
      const url = `${targetUrl}${targetUrl.includes("?") ? "&" : "?"}ts=${Date.now()}`;
      const res = await fetch(url, { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const data = await res.json();
      const merged = {
        ...emptyDashboard,
        ...data,
        meta: { ...emptyDashboard.meta, ...(data.meta || {}) },
        metrics: { ...emptyDashboard.metrics, ...(data.metrics || {}) },
        marketFunnel: { ...emptyDashboard.marketFunnel, ...(data.marketFunnel || {}) },
        performance: { ...emptyDashboard.performance, ...(data.performance || {}) },
      };

      setDashboard(merged);
      setFetchMessage(`Connected to ${targetUrl}`);
      localStorage.setItem("snitch-dashboard-url", targetUrl);
      localStorage.setItem("snitch-dashboard-data", JSON.stringify(merged));
    } catch (error) {
      const cached = localStorage.getItem("snitch-dashboard-data");
      if (cached) {
        try {
          const parsed = JSON.parse(cached);
          setDashboard(parsed);
          setFetchMessage(`Live fetch failed, using cached data (${error.message})`);
        } catch {
          setFetchMessage(`Load failed: ${error.message}`);
        }
      } else {
        setFetchMessage(`Load failed: ${error.message}`);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const cached = localStorage.getItem("snitch-dashboard-data");
    if (cached) {
      try {
        setDashboard(JSON.parse(cached));
      } catch {
        // ignore bad cache
      }
    }
    fetchDashboard(dataUrl);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!autoRefresh) return;
    const timer = setInterval(() => {
      fetchDashboard(dataUrl);
    }, 60000);
    return () => clearInterval(timer);
  }, [autoRefresh, dataUrl]);

  return {
    dashboard,
    dataUrl,
    setDataUrl,
    fetchDashboard,
    loading,
    fetchMessage,
    autoRefresh,
    setAutoRefresh,
    technicalOpen,
    setTechnicalOpen,
  };
}

function MetricCard({ label, value, icon }) {
  return (
    <Card className="rounded-3xl border-slate-800 bg-slate-950/70 shadow-2xl">
      <CardContent className="p-5">
        <div className="mb-3 flex items-center gap-2 text-slate-400">
          {icon}
          <span className="text-sm uppercase tracking-wide">{label}</span>
        </div>
        <div className="text-3xl font-bold text-slate-100">{value}</div>
      </CardContent>
    </Card>
  );
}

function TinyInfo({ label, value, valueClassName = "text-slate-100" }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
      <div className="text-sm text-slate-400">{label}</div>
      <div className={cn("mt-2 text-xl font-semibold", valueClassName)}>{value}</div>
    </div>
  );
}

function MiniPlan({ label, value }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-4">
      <div className="text-sm text-slate-400">{label}</div>
      <div className="mt-2 text-xl font-medium text-slate-100">{value}</div>
    </div>
  );
}

function InfoBlock({ title, value }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-4">
      <div className="mb-2 text-sm uppercase tracking-wide text-slate-400">{title}</div>
      <div className="text-lg leading-8 text-slate-100">{value}</div>
    </div>
  );
}

function SectionHeader({ icon, title, desc }) {
  return (
    <div className="mb-5">
      <div className="flex items-center gap-3">
        {icon}
        <h2 className="text-4xl font-bold text-slate-50">{title}</h2>
      </div>
      <p className="mt-2 text-xl text-slate-400">{desc}</p>
    </div>
  );
}

function EmptyState({ text = "No clean setup in this section right now." }) {
  return (
    <Card className="rounded-3xl border-slate-800 bg-slate-950/50 shadow-2xl">
      <CardContent className="p-10 text-3xl text-slate-400">{text}</CardContent>
    </Card>
  );
}

function TokenCard({ item, onSelect, selected }) {
  return (
    <Card
      onClick={() => onSelect?.(item)}
      className={cn(
        "cursor-pointer rounded-3xl border bg-slate-950/70 shadow-2xl transition-all duration-200",
        selected ? "border-cyan-400/50 ring-1 ring-cyan-400/40" : "border-slate-800 hover:border-slate-700"
      )}
    >
      <CardContent className="space-y-4 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-4xl font-bold text-slate-50">{item.token}</div>
            <div className="mt-1 text-xl text-slate-400">{item.pair}</div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge className={cn("rounded-full border px-4 py-2 text-sm", badgeClass(item.actionShort))}>
              {item.actionShort}
            </Badge>
            {item.entryType && (
              <Badge className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-4 py-2 text-sm text-cyan-300">
                {item.entryType}
              </Badge>
            )}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <TinyInfo label="Score" value={fmtPlain(item.score)} valueClassName={scoreTone(item.score)} />
          <TinyInfo label="Risk" value={item.risk} valueClassName={riskTextClass(item.risk)} />
        </div>

        <div>
          <div className="mb-2 flex items-center justify-between text-slate-400">
            <span>Signal Strength</span>
            <span>{Math.round(toNumber(item.score) * 10)}/100</span>
          </div>
          <div className="h-3 overflow-hidden rounded-full bg-slate-800">
            <div
              className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-teal-300"
              style={{ width: `${Math.max(8, Math.min(100, Math.round(toNumber(item.score) * 10)))}%` }}
            />
          </div>
        </div>

        <div className="text-2xl leading-10 text-slate-200">{item.why}</div>

        <div className="grid grid-cols-2 gap-4">
          <TinyInfo label="Trade USD" value={fmtCompactUsd(item.tradeUsd)} />
          <TinyInfo label="Impact" value={fmtPercent(item.impactPct)} />
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          <MiniPlan label="Buy Zone" value={fmtZone(item.buyZone)} />
          <MiniPlan label="Breakout" value={fmtPrice(item.breakoutTrigger)} />
          <MiniPlan label="Invalidation" value={fmtPrice(item.invalidation)} />
          <MiniPlan label="TP1 / TP2" value={`${fmtPrice(item.tp1)} / ${fmtPrice(item.tp2)}`} />
          <MiniPlan label="RR" value={fmtRR(item.rr)} />
          <MiniPlan label="Sector" value={item.sector || "General"} />
        </div>

        <div className="flex flex-wrap gap-3">
          <Button className="rounded-2xl bg-white text-slate-950 hover:bg-slate-100">
            <Eye className="mr-2 h-4 w-4" />
            Open Detail
          </Button>
          <Button variant="outline" className="rounded-2xl border-slate-700 bg-transparent text-slate-100 hover:bg-slate-900">
            <Zap className="mr-2 h-4 w-4" />
            Set Alert
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function ExecutionPlan({ item }) {
  if (!item) {
    return (
      <Card className="h-full rounded-3xl border-slate-800 bg-slate-950/70 shadow-2xl">
        <CardContent className="flex h-full min-h-[320px] items-center justify-center p-8 text-center text-slate-400">
          Select a token card to view the full action plan.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="h-full rounded-3xl border-slate-800 bg-slate-950/70 shadow-2xl">
      <CardHeader className="border-b border-slate-800 pb-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="text-4xl font-bold text-slate-50">{item.token}</CardTitle>
            <CardDescription className="mt-2 text-xl text-slate-400">
              {item.pair} · {item.direction}
            </CardDescription>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge className={cn("rounded-full border px-4 py-2 text-sm", badgeClass(item.actionShort))}>
              {item.actionShort}
            </Badge>
            <Badge className={cn("rounded-full border px-4 py-2 text-sm", riskBadgeClass(item.risk))}>
              {item.risk}
            </Badge>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-5 p-6">
        <div className="grid gap-4 md:grid-cols-3">
          <TinyInfo label="Action Score" value={fmtPlain(item.score)} valueClassName={scoreTone(item.score)} />
          <TinyInfo label="Liquidity Impact" value={fmtPercent(item.impactPct)} />
          <TinyInfo label="Trade Value" value={fmtCompactUsd(item.tradeUsd)} />
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <TinyInfo label="Trend" value={String(item.trend || "neutral").toUpperCase()} />
          <TinyInfo label="Sector" value={item.sector || "General"} />
          <TinyInfo label="Entry Type" value={item.entryType || "Watch"} />
          <TinyInfo label="RR" value={fmtRR(item.rr)} />
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <TinyInfo label="Buy Zone" value={fmtZone(item.buyZone)} />
          <TinyInfo label="Breakout Trigger" value={fmtPrice(item.breakoutTrigger)} />
          <TinyInfo label="Invalidation" value={fmtPrice(item.invalidation)} />
          <TinyInfo label="TP1 / TP2" value={`${fmtPrice(item.tp1)} / ${fmtPrice(item.tp2)}`} />
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <Card className="rounded-3xl border-slate-800 bg-slate-900/50">
            <CardContent className="space-y-4 p-5">
              <InfoBlock title="Action Now" value={item.action} />
              <InfoBlock title="What it means" value={item.why} />
              <InfoBlock title="What to do next" value={item.nextStep} />
              <InfoBlock title="Do not do" value={item.doNot} />
              <InfoBlock title="Cancel plan if" value={item.cancelIf} />
            </CardContent>
          </Card>

          <Card className="rounded-3xl border-slate-800 bg-slate-900/50">
            <CardContent className="space-y-4 p-5">
              <InfoBlock title="Why this is cheap" value={item.whyCheap || "N/A"} />
              <InfoBlock title="Tradability" value={item.exchangeText || "Unknown"} />
              <InfoBlock title="Confidence" value={item.confidence || "N/A"} />
              <InfoBlock title="Trap reason" value={item.trapReason || "No major trap flagged"} />
            </CardContent>
          </Card>
        </div>

        {safeArray(item.history).length > 0 && (
          <Card className="rounded-3xl border-slate-800 bg-slate-900/50">
            <CardHeader>
              <CardTitle className="text-lg text-slate-100">Micro Structure Snapshot</CardTitle>
              <CardDescription className="text-slate-400">Recent score history from the current engine.</CardDescription>
            </CardHeader>
            <CardContent className="h-56 p-2">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={item.history}>
                  <defs>
                    <linearGradient id={`hist-${item.token}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#34d399" stopOpacity={0.45} />
                      <stop offset="95%" stopColor="#34d399" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="d" stroke="#94a3b8" />
                  <YAxis stroke="#94a3b8" />
                  <Tooltip
                    contentStyle={{
                      background: "#020617",
                      border: "1px solid #334155",
                      borderRadius: "16px",
                      color: "#e2e8f0",
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="score"
                    stroke="#34d399"
                    fill={`url(#hist-${item.token})`}
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        )}
      </CardContent>
    </Card>
  );
}

function RejectReasonsCard({ reasons }) {
  const entries = Object.entries(reasons || {})
    .map(([name, value]) => ({ name, value: toNumber(value) }))
    .filter((x) => x.value > 0)
    .sort((a, b) => b.value - a.value);

  return (
    <Card className="rounded-3xl border-slate-800 bg-slate-950/70 shadow-2xl">
      <CardHeader>
        <CardTitle className="flex items-center gap-3 text-4xl text-slate-50">
          <ShieldAlert className="h-6 w-6 text-rose-300" />
          Reject Reasons
        </CardTitle>
        <CardDescription className="text-xl text-slate-400">
          Why the engine filtered names out before showing them.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {entries.length === 0 ? (
          <div className="text-slate-400">No reject reasons available.</div>
        ) : (
          entries.map((item) => (
            <div key={item.name} className="rounded-3xl border border-slate-800 bg-slate-900/50 p-5">
              <div className="text-lg uppercase tracking-wide text-slate-400">{item.name.replaceAll("_", " ")}</div>
              <div className="mt-3 text-5xl font-bold text-rose-300">{item.value}</div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

function PotentialTokenTable({ items, onQuickSelect }) {
  return (
    <Card className="rounded-3xl border-slate-800 bg-slate-950/70 shadow-2xl">
      <CardHeader>
        <CardTitle className="text-4xl text-slate-50">Potential Tokens</CardTitle>
        <CardDescription className="text-xl text-slate-400">
          Broader opportunities beyond the current qualified shortlist.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {items.length === 0 ? (
          <div className="text-slate-400">No potential tokens found right now.</div>
        ) : (
          items.map((item) => (
            <div
              key={item.token}
              className="cursor-pointer rounded-3xl border border-slate-800 bg-slate-900/50 p-5 hover:border-slate-700"
              onClick={() => onQuickSelect?.(item.token)}
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="text-3xl font-bold text-slate-100">{item.token}</div>
                  <div className="mt-2 text-lg text-slate-400">{item.thesis}</div>
                </div>
                <Badge className="rounded-full border border-slate-700 bg-slate-950/70 px-4 py-2 text-sm text-slate-200">
                  {item.confidence}
                </Badge>
              </div>

              <div className="mt-4 grid gap-3 md:grid-cols-3 xl:grid-cols-6">
                <MiniPlan label="Price" value={item.price || "N/A"} />
                <MiniPlan label="FDV" value={item.fdv || "N/A"} />
                <MiniPlan label="Liquidity" value={item.liquidity || "N/A"} />
                <MiniPlan label="24H Volume" value={item.volume24h || "N/A"} />
                <MiniPlan label="Stage" value={item.listingStage || "N/A"} />
                <MiniPlan label="Tradability" value={item.exchange || "N/A"} />
              </div>

              <div className="mt-4 grid gap-3 md:grid-cols-3">
                <MiniPlan label="Buy Zone" value={fmtZone(item.buyZone)} />
                <MiniPlan label="Breakout" value={fmtPrice(item.breakoutTrigger)} />
                <MiniPlan label="RR" value={fmtRR(item.rr)} />
              </div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

function PresaleTable({ items }) {
  return (
    <Card className="rounded-3xl border-slate-800 bg-slate-950/70 shadow-2xl">
      <CardHeader>
        <CardTitle className="text-4xl text-slate-50">Presale Watchlist</CardTitle>
        <CardDescription className="text-xl text-slate-400">
          Curated names to review manually before any capital decision.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {items.length === 0 ? (
          <div className="text-slate-400">No presale list available.</div>
        ) : (
          items.map((item) => (
            <div key={item.project} className="rounded-3xl border border-slate-800 bg-slate-900/50 p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="text-3xl font-bold text-slate-100">{item.project}</div>
                  <div className="mt-1 text-lg text-slate-400">
                    {item.stage} · {item.launchDate}
                  </div>
                </div>
                <Badge className={cn("rounded-full border px-4 py-2 text-sm", badgeClass(item.action))}>
                  {item.action}
                </Badge>
              </div>

              <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
                <MiniPlan label="Trust Score" value={String(item.trustScore)} />
                <MiniPlan label="Tokenomics Score" value={String(item.tokenomicsScore)} />
                <MiniPlan label="Vesting" value={item.vesting} />
                <MiniPlan label="Audit" value={item.audit} />
                <MiniPlan label="Red Flags" value={item.redFlags} />
              </div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

function RecentSignalsCard({ items }) {
  return (
    <Card className="rounded-3xl border-slate-800 bg-slate-950/70 shadow-2xl">
      <CardHeader>
        <CardTitle className="text-4xl text-slate-50">Recent Qualified Signals</CardTitle>
        <CardDescription className="text-xl text-slate-400">
          Latest filtered signals worth attention.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {items.length === 0 ? (
          <div className="text-slate-400">No recent signals available.</div>
        ) : (
          items.map((item, idx) => (
            <div key={`${item.token}-${idx}`} className="rounded-3xl border border-slate-800 bg-slate-900/50 p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="text-3xl font-bold text-slate-100">{item.token}</div>
                  <div className="mt-1 text-lg text-slate-400">{item.pair} · {item.direction}</div>
                </div>
                <Badge className={cn("rounded-full border px-4 py-2 text-sm", badgeClass(item.action))}>
                  {item.action}
                </Badge>
              </div>

              <div className="mt-4 grid gap-3 md:grid-cols-3">
                <MiniPlan label="Score" value={fmtPlain(item.score)} />
                <MiniPlan label="Impact" value={item.impact} />
                <MiniPlan label="USD" value={item.usd} />
              </div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

function ProofCard({ items }) {
  return (
    <Card className="rounded-3xl border-slate-800 bg-slate-950/70 shadow-2xl">
      <CardHeader>
        <CardTitle className="text-4xl text-slate-50">Proof Snapshot</CardTitle>
        <CardDescription className="text-xl text-slate-400">
          Quick performance metrics.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4 md:grid-cols-2">
        {items.length === 0 ? (
          <div className="text-slate-400">No proof metrics available.</div>
        ) : (
          items.map((item) => (
            <div key={item.metric} className="rounded-3xl border border-slate-800 bg-slate-900/50 p-5">
              <div className="text-lg text-slate-400">{item.metric}</div>
              <div className="mt-2 text-5xl font-bold text-slate-100">{item.value}</div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

function ScoreTrendCard({ data }) {
  return (
    <Card className="rounded-3xl border-slate-800 bg-slate-950/70 shadow-2xl">
      <CardHeader>
        <CardTitle className="text-4xl text-slate-50">Performance Matrix</CardTitle>
        <CardDescription className="text-xl text-slate-400">
          Focus, emerging, and caution trend over recent sessions.
        </CardDescription>
      </CardHeader>
      <CardContent className="h-[360px] p-2">
        {data.length === 0 ? (
          <div className="flex h-full items-center justify-center text-slate-400">No score trend available.</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="name" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" />
              <Tooltip
                contentStyle={{
                  background: "#020617",
                  border: "1px solid #334155",
                  borderRadius: "16px",
                  color: "#e2e8f0",
                }}
              />
              <Bar dataKey="focus" fill="#22c55e" radius={[8, 8, 0, 0]} />
              <Bar dataKey="emerging" fill="#f59e0b" radius={[8, 8, 0, 0]} />
              <Bar dataKey="caution" fill="#ef4444" radius={[8, 8, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}

function ActionMixCard({ data }) {
  return (
    <Card className="rounded-3xl border-slate-800 bg-slate-950/70 shadow-2xl">
      <CardHeader>
        <CardTitle className="text-4xl text-slate-50">Action Mix</CardTitle>
        <CardDescription className="text-xl text-slate-400">
          Distribution of current dashboard actions.
        </CardDescription>
      </CardHeader>
      <CardContent className="h-[360px] p-2">
        {data.length === 0 ? (
          <div className="flex h-full items-center justify-center text-slate-400">No action mix available.</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Tooltip
                contentStyle={{
                  background: "#020617",
                  border: "1px solid #334155",
                  borderRadius: "16px",
                  color: "#e2e8f0",
                }}
              />
              <Pie
                data={data}
                dataKey="value"
                nameKey="name"
                innerRadius={80}
                outerRadius={120}
                paddingAngle={3}
              >
                {data.map((entry, idx) => (
                  <Cell key={`${entry.name}-${idx}`} fill={["#22c55e", "#f59e0b", "#ef4444", "#38bdf8"][idx % 4]} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  );
}

export default function App() {
  const {
    dashboard,
    dataUrl,
    setDataUrl,
    fetchDashboard,
    loading,
    fetchMessage,
    autoRefresh,
    setAutoRefresh,
    technicalOpen,
    setTechnicalOpen,
  } = useDashboardData();

  const [query, setQuery] = useState("");
  const [tab, setTab] = useState("focus");
  const [selectedToken, setSelectedToken] = useState(null);

  const tradeFocusNow = safeArray(dashboard.tradeFocusNow);
  const executionReady = safeArray(dashboard.executionReady);
  const majorMonitor = safeArray(dashboard.majorMonitor);
  const topSniperPicks = safeArray(dashboard.topSniperPicks);
  const emergingPotential = safeArray(dashboard.emergingPotential);
  const cautionAvoid = safeArray(dashboard.cautionAvoid);
  const potentialTokens = safeArray(dashboard.potentialTokens);
  const presaleWatchlist = safeArray(dashboard.presaleWatchlist);
  const recentSignals = safeArray(dashboard.recentSignals);
  const scoreTrend = safeArray(dashboard.performance?.scoreTrend);
  const actionMix = safeArray(dashboard.performance?.actionMix);
  const proof = safeArray(dashboard.performance?.proof);

  useEffect(() => {
    const firstCandidate =
      executionReady[0] ||
      topSniperPicks[0] ||
      tradeFocusNow[0] ||
      emergingPotential[0] ||
      cautionAvoid[0] ||
      majorMonitor[0] ||
      null;
    setSelectedToken(firstCandidate);
  }, [dashboard]);

  const allCards = useMemo(() => {
    const map = new Map();
    [
      ...tradeFocusNow,
      ...executionReady,
      ...topSniperPicks,
      ...majorMonitor,
      ...emergingPotential,
      ...cautionAvoid,
    ].forEach((item) => {
      if (!item?.token) return;
      map.set(item.token, item);
    });
    return [...map.values()];
  }, [tradeFocusNow, executionReady, topSniperPicks, majorMonitor, emergingPotential, cautionAvoid]);

  const filteredList = useMemo(() => {
    const q = query.trim().toLowerCase();
    const base =
      tab === "focus"
        ? tradeFocusNow
        : tab === "emerging"
        ? emergingPotential
        : cautionAvoid;

    if (!q) return base;
    return base.filter((item) => {
      const hay = `${item.token} ${item.pair} ${item.actionShort} ${item.sector} ${item.entryType}`.toLowerCase();
      return hay.includes(q);
    });
  }, [tab, query, tradeFocusNow, emergingPotential, cautionAvoid]);

  const handleQuickSelectPotential = (token) => {
    const found = allCards.find((x) => x.token === token);
    if (found) {
      setSelectedToken(found);
      return;
    }
    setQuery(token);
  };

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(16,185,129,0.15),_transparent_20%),radial-gradient(circle_at_top,_rgba(6,182,212,0.12),_transparent_25%),linear-gradient(180deg,#020617_0%,#020617_100%)] text-slate-100">
      <div className="mx-auto max-w-[1700px] px-4 py-5 md:px-8 md:py-8">
        <Card className="overflow-hidden rounded-[36px] border-slate-800 bg-slate-950/60 shadow-[0_0_80px_rgba(0,0,0,0.35)]">
          <div className="border-b border-slate-800 bg-[radial-gradient(circle_at_top,_rgba(16,185,129,0.16),_transparent_18%),linear-gradient(90deg,rgba(2,6,23,1)_0%,rgba(2,6,23,0.96)_50%,rgba(2,6,23,1)_100%)] p-4 md:p-8">
            <div className="flex flex-col gap-6 xl:flex-row xl:items-start xl:justify-between">
              <div className="max-w-4xl">
                <div className="flex items-start gap-4">
                  <div className="rounded-3xl border border-emerald-500/30 bg-emerald-500/10 p-4">
                    <Radar className="h-8 w-8 text-emerald-300" />
                  </div>
                  <div>
                    <h1 className="text-5xl font-bold tracking-tight text-slate-50 md:text-7xl">
                      {dashboard.meta?.product || "SNITCH Alert Dashboard"}
                    </h1>
                    <p className="mt-2 text-2xl text-slate-400 md:text-3xl">
                      Dark premium signal workspace for fast trading decisions
                    </p>
                  </div>
                </div>

                <div className="mt-6 flex flex-wrap gap-3">
                  <Badge className="rounded-full border border-slate-700 bg-slate-950/70 px-4 py-2 text-base text-slate-200">
                    <Clock3 className="mr-2 h-4 w-4" />
                    Last sync: {dashboard.meta?.asOf}
                  </Badge>
                  <Badge className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-base text-emerald-300">
                    {dashboard.meta?.marketBias}
                  </Badge>
                  <Badge className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-base text-emerald-300">
                    {dashboard.meta?.mode}
                  </Badge>
                  <Badge className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-base text-emerald-300">
                    {autoRefresh ? "Auto refresh on" : "Auto refresh off"}
                  </Badge>
                </div>
              </div>
            </div>

            <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-6">
              <MetricCard label="Qualified" value={dashboard.metrics?.qualifiedSignals ?? 0} icon={<Signal className="h-4 w-4" />} />
              <MetricCard label="Focus" value={dashboard.metrics?.tradeFocus ?? 0} icon={<Target className="h-4 w-4" />} />
              <MetricCard label="Emerging" value={dashboard.metrics?.emerging ?? 0} icon={<Rocket className="h-4 w-4" />} />
              <MetricCard label="Caution" value={dashboard.metrics?.caution ?? 0} icon={<AlertTriangle className="h-4 w-4" />} />
              <MetricCard label="Avg Confidence" value={`${dashboard.metrics?.avgConfidence ?? 0}%`} icon={<GaugeIcon />} />
              <MetricCard label="30D Win Rate" value={`${dashboard.metrics?.winRate30d ?? 0}%`} icon={<TrendingUp className="h-4 w-4" />} />
            </div>
          </div>

          <div className="space-y-8 p-4 md:p-8">
            <Card className="rounded-3xl border-slate-800 bg-slate-950/70 shadow-2xl">
              <CardHeader>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <CardTitle className="flex items-center gap-3 text-4xl text-slate-50">
                    <Database className="h-6 w-6 text-slate-300" />
                    Data Source
                  </CardTitle>
                  <Button
                    variant="outline"
                    onClick={() => setTechnicalOpen((s) => !s)}
                    className="rounded-full border-slate-700 bg-transparent text-slate-100 hover:bg-slate-900"
                  >
                    {technicalOpen ? "Hide technical tools" : "Show technical tools"}
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="rounded-3xl border border-slate-800 bg-slate-900/50 p-5">
                  <div className="text-lg font-medium text-slate-200">Current status</div>
                  <div className="mt-2 text-xl text-slate-400">{fetchMessage}</div>
                  <div className="mt-3 text-base text-slate-500">{dashboard.meta?.dataSource}</div>
                </div>

                {technicalOpen && (
                  <>
                    <div className="flex flex-col gap-3 xl:flex-row">
                      <div className="flex-1">
                        <Input
                          value={dataUrl}
                          onChange={(e) => setDataUrl(e.target.value)}
                          placeholder="/snitch-dashboard-v2/data/dashboard-current.json"
                          className="h-14 rounded-2xl border-slate-800 bg-slate-900 text-lg text-slate-100"
                        />
                      </div>
                      <Button
                        onClick={() => fetchDashboard(dataUrl)}
                        disabled={loading}
                        className="h-14 rounded-2xl bg-white px-6 text-lg text-slate-950 hover:bg-slate-100"
                      >
                        {loading ? "Connecting..." : "Connect"}
                      </Button>
                    </div>

                    <div className="flex flex-wrap gap-3">
                      <Button
                        variant="outline"
                        onClick={() => setAutoRefresh((s) => !s)}
                        className="rounded-2xl border-slate-700 bg-transparent text-slate-100 hover:bg-slate-900"
                      >
                        <Clock3 className="mr-2 h-4 w-4" />
                        {autoRefresh ? "Auto Refresh On" : "Auto Refresh Off"}
                      </Button>

                      <Button
                        variant="outline"
                        onClick={() => fetchDashboard(dataUrl)}
                        className="rounded-2xl border-slate-700 bg-transparent text-slate-100 hover:bg-slate-900"
                      >
                        <Database className="mr-2 h-4 w-4" />
                        Load JSON
                      </Button>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>

            <div className="grid gap-6 xl:grid-cols-3">
              <Card className="rounded-3xl border-slate-800 bg-slate-950/70 shadow-2xl xl:col-span-2">
                <CardHeader>
                  <CardTitle className="flex items-center gap-3 text-4xl text-slate-50">
                    <CheckCircle2 className="h-6 w-6 text-emerald-300" />
                    Execution Ready
                  </CardTitle>
                  <CardDescription className="text-xl text-slate-400">
                    Cleanest active setups with usable zones and invalidation.
                  </CardDescription>
                </CardHeader>
                <CardContent className="grid gap-4 md:grid-cols-2">
                  {executionReady.length === 0 ? (
                    <div className="text-slate-400">No execution-ready setup right now.</div>
                  ) : (
                    executionReady.map((item) => (
                      <TokenCard
                        key={`execution-${item.token}`}
                        item={item}
                        onSelect={setSelectedToken}
                        selected={selectedToken?.token === item.token}
                      />
                    ))
                  )}
                </CardContent>
              </Card>

              <Card className="rounded-3xl border-slate-800 bg-slate-950/70 shadow-2xl">
                <CardHeader>
                  <CardTitle className="flex items-center gap-3 text-4xl text-slate-50">
                    <Rocket className="h-6 w-6 text-emerald-300" />
                    Top Sniper Picks
                  </CardTitle>
                  <CardDescription className="text-xl text-slate-400">
                    Best current names combining score, impact, and practical opportunity.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {topSniperPicks.length === 0 ? (
                    <div className="text-slate-400">No sniper picks right now.</div>
                  ) : (
                    topSniperPicks.map((item, index) => (
                      <div
                        key={`sniper-${item.token}`}
                        className="cursor-pointer rounded-3xl border border-slate-800 bg-slate-900/50 p-5 hover:border-slate-700"
                        onClick={() => setSelectedToken(item)}
                      >
                        <div className="mb-4 flex items-start justify-between gap-3">
                          <div>
                            <div className="text-4xl font-bold text-slate-50">{item.token}</div>
                            <div className="mt-1 text-xl text-slate-400">{item.pair}</div>
                          </div>
                          <Badge className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-300">
                            #{index + 1}
                          </Badge>
                        </div>

                        <div className="grid gap-3 md:grid-cols-2">
                          <MiniPlan label="Score" value={fmtPlain(item.score)} />
                          <MiniPlan label="Impact" value={fmtPercent(item.impactPct)} />
                        </div>

                        <div className="mt-4 text-lg leading-8 text-slate-300">{item.why}</div>
                      </div>
                    ))
                  )}
                </CardContent>
              </Card>
            </div>

            <div className="grid gap-6 xl:grid-cols-2">
              <RejectReasonsCard reasons={dashboard.marketFunnel?.rejectReasons} />

              <Card className="rounded-3xl border-slate-800 bg-slate-950/70 shadow-2xl">
                <CardHeader>
                  <CardTitle className="flex items-center gap-3 text-4xl text-slate-50">
                    <LineChart className="h-6 w-6 text-cyan-300" />
                    Tradeable Majors
                  </CardTitle>
                  <CardDescription className="text-xl text-slate-400">
                    Higher-liquidity names to monitor for cleaner execution and market tone.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {majorMonitor.length === 0 ? (
                    <div className="text-slate-400">No major monitor assets available.</div>
                  ) : (
                    majorMonitor.map((item) => (
                      <div
                        key={`major-${item.token}`}
                        className="cursor-pointer rounded-3xl border border-slate-800 bg-slate-900/50 p-5 hover:border-slate-700"
                        onClick={() => setSelectedToken(item)}
                      >
                        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <div className="text-3xl font-bold text-slate-50">{item.token} <span className="font-normal text-slate-500">· {item.pair}</span></div>
                            <div className="mt-1 text-xl text-slate-400">{item.direction}</div>
                          </div>
                          <Badge className={cn("rounded-full border px-4 py-2 text-sm", badgeClass(item.actionShort))}>
                            {item.actionShort}
                          </Badge>
                        </div>

                        <div className="grid gap-3 md:grid-cols-3">
                          <MiniPlan label="Score" value={fmtPlain(item.score)} />
                          <MiniPlan label="Impact" value={fmtPercent(item.impactPct)} />
                          <MiniPlan label="USD" value={fmtCompactUsd(item.tradeUsd)} />
                        </div>
                      </div>
                    ))
                  )}
                </CardContent>
              </Card>
            </div>

            <div className="grid gap-6 xl:grid-cols-2">
              <Card className="rounded-3xl border-slate-800 bg-slate-950/70 shadow-2xl">
                <CardHeader>
                  <CardTitle className="flex items-center gap-3 text-4xl text-slate-50">
                    <Search className="h-6 w-6 text-slate-300" />
                    Search & Filter
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-col gap-4 xl:flex-row">
                    <div className="relative flex-1">
                      <Search className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-500" />
                      <Input
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder="Search token, pair, action"
                        className="h-14 rounded-2xl border-slate-800 bg-slate-900 pl-12 text-lg text-slate-100"
                      />
                    </div>
                    <Button variant="outline" className="h-14 rounded-2xl border-slate-700 bg-transparent px-6 text-slate-100 hover:bg-slate-900">
                      <Filter className="mr-2 h-4 w-4" />
                      Filter
                    </Button>
                  </div>
                </CardContent>
              </Card>

              <Card className="rounded-3xl border-slate-800 bg-slate-950/70 shadow-2xl">
                <CardContent className="p-6">
                  <div className="text-3xl font-semibold text-slate-50">How to use this</div>
                  <div className="mt-3 text-xl leading-9 text-slate-300">
                    Focus means highest-priority setups to inspect now. Emerging means promising but not fully
                    confirmed. Caution means avoid new exposure or reduce risk.
                  </div>
                </CardContent>
              </Card>
            </div>

            <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
              <div className="space-y-6">
                <Tabs value={tab} onValueChange={setTab}>
                  <TabsList className="grid h-16 w-full grid-cols-3 rounded-full border border-slate-800 bg-slate-950/60">
                    <TabsTrigger value="focus" className="rounded-full text-xl data-[state=active]:bg-slate-900 data-[state=active]:text-white">
                      Trade Focus
                    </TabsTrigger>
                    <TabsTrigger value="emerging" className="rounded-full text-xl data-[state=active]:bg-slate-900 data-[state=active]:text-white">
                      Emerging
                    </TabsTrigger>
                    <TabsTrigger value="caution" className="rounded-full text-xl data-[state=active]:bg-slate-900 data-[state=active]:text-white">
                      Caution
                    </TabsTrigger>
                  </TabsList>
                </Tabs>

                {tab === "focus" && (
                  <>
                    <SectionHeader
                      icon={<Target className="h-5 w-5 text-emerald-300" />}
                      title="Trade Focus Now"
                      desc="Highest priority names to monitor immediately."
                    />
                    {filteredList.length === 0 ? (
                      <EmptyState />
                    ) : (
                      <div className="grid gap-5 xl:grid-cols-2">
                        {filteredList.map((item) => (
                          <TokenCard
                            key={`focus-${item.token}`}
                            item={item}
                            onSelect={setSelectedToken}
                            selected={selectedToken?.token === item.token}
                          />
                        ))}
                      </div>
                    )}
                  </>
                )}

                {tab === "emerging" && (
                  <>
                    <SectionHeader
                      icon={<Rocket className="h-5 w-5 text-amber-300" />}
                      title="Emerging Potential"
                      desc="Early setups that still need confirmation."
                    />
                    {filteredList.length === 0 ? (
                      <EmptyState />
                    ) : (
                      <div className="grid gap-5 xl:grid-cols-2">
                        {filteredList.map((item) => (
                          <TokenCard
                            key={`emerging-${item.token}`}
                            item={item}
                            onSelect={setSelectedToken}
                            selected={selectedToken?.token === item.token}
                          />
                        ))}
                      </div>
                    )}
                  </>
                )}

                {tab === "caution" && (
                  <>
                    <SectionHeader
                      icon={<ShieldAlert className="h-5 w-5 text-rose-300" />}
                      title="Caution / Avoid"
                      desc="Risky or bearish structures that need caution."
                    />
                    {filteredList.length === 0 ? (
                      <EmptyState />
                    ) : (
                      <div className="grid gap-5 xl:grid-cols-2">
                        {filteredList.map((item) => (
                          <TokenCard
                            key={`caution-${item.token}`}
                            item={item}
                            onSelect={setSelectedToken}
                            selected={selectedToken?.token === item.token}
                          />
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>

              <ExecutionPlan item={selectedToken} />
            </div>

            <div className="grid gap-6 xl:grid-cols-2">
              <ActionMixCard data={actionMix} />
              <ScoreTrendCard data={scoreTrend} />
            </div>

            <div className="grid gap-6 xl:grid-cols-2">
              <ProofCard items={proof} />
              <RecentSignalsCard items={recentSignals} />
            </div>

            <div className="grid gap-6 xl:grid-cols-2">
              <PotentialTokenTable items={potentialTokens} onQuickSelect={handleQuickSelectPotential} />
              <PresaleTable items={presaleWatchlist} />
            </div>

            <div className="grid gap-4 md:grid-cols-4">
              <Card className="rounded-3xl border-slate-800 bg-slate-950/70 shadow-2xl">
                <CardContent className="p-5">
                  <div className="mb-3 flex items-center gap-2 text-slate-400">
                    <Database className="h-4 w-4" />
                    <span className="text-sm uppercase tracking-wide">Scanned</span>
                  </div>
                  <div className="text-4xl font-bold text-slate-100">{dashboard.marketFunnel?.scanned ?? 0}</div>
                </CardContent>
              </Card>

              <Card className="rounded-3xl border-slate-800 bg-slate-950/70 shadow-2xl">
                <CardContent className="p-5">
                  <div className="mb-3 flex items-center gap-2 text-slate-400">
                    <AlertTriangle className="h-4 w-4" />
                    <span className="text-sm uppercase tracking-wide">Rejected</span>
                  </div>
                  <div className="text-4xl font-bold text-rose-300">{dashboard.marketFunnel?.rejected ?? 0}</div>
                </CardContent>
              </Card>

              <Card className="rounded-3xl border-slate-800 bg-slate-950/70 shadow-2xl">
                <CardContent className="p-5">
                  <div className="mb-3 flex items-center gap-2 text-slate-400">
                    <CheckCircle2 className="h-4 w-4" />
                    <span className="text-sm uppercase tracking-wide">Qualified</span>
                  </div>
                  <div className="text-4xl font-bold text-emerald-300">{dashboard.marketFunnel?.qualified ?? 0}</div>
                </CardContent>
              </Card>

              <Card className="rounded-3xl border-slate-800 bg-slate-950/70 shadow-2xl">
                <CardContent className="p-5">
                  <div className="mb-3 flex items-center gap-2 text-slate-400">
                    <Wallet className="h-4 w-4" />
                    <span className="text-sm uppercase tracking-wide">Displayed</span>
                  </div>
                  <div className="text-4xl font-bold text-amber-300">{dashboard.marketFunnel?.displayed ?? 0}</div>
                </CardContent>
              </Card>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
