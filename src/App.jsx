import React, { useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
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
  ShieldAlert,
  Coins,
  LineChart,
  Layers3,
} from "lucide-react";

const starterData = {
  meta: {
    product: "SNITCH Alert Dashboard",
    mode: "Live Monitor",
    marketBias: "Neutral",
    asOf: "Bootstrapped",
    dataSource: "seed",
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

function normalizeIncomingData(raw) {
  if (!raw || typeof raw !== "object") return starterData;
  return {
    meta: { ...starterData.meta, ...(raw.meta || {}) },
    metrics: { ...starterData.metrics, ...(raw.metrics || {}) },
    marketFunnel: { ...starterData.marketFunnel, ...(raw.marketFunnel || {}) },
    tradeFocusNow: Array.isArray(raw.tradeFocusNow) ? raw.tradeFocusNow : [],
    emergingPotential: Array.isArray(raw.emergingPotential) ? raw.emergingPotential : [],
    cautionAvoid: Array.isArray(raw.cautionAvoid) ? raw.cautionAvoid : [],
    potentialTokens: Array.isArray(raw.potentialTokens) ? raw.potentialTokens : [],
    presaleWatchlist: Array.isArray(raw.presaleWatchlist) ? raw.presaleWatchlist : [],
    recentSignals: Array.isArray(raw.recentSignals) ? raw.recentSignals : [],
    performance: {
      ...starterData.performance,
      ...(raw.performance || {}),
    },
  };
}

function fmtUsd(v) {
  if (typeof v !== "number") return v;
  if (Math.abs(v) >= 1_000_000_000) return `$${(v / 1_000_000_000).toFixed(2)}B`;
  if (Math.abs(v) >= 1_000_000) return `$${(v / 1_000_000).toFixed(2)}M`;
  if (Math.abs(v) >= 1_000) return `$${(v / 1_000).toFixed(2)}K`;
  return `$${v.toFixed(2)}`;
}

function scoreColor(score) {
  if (score >= 7) return "text-emerald-400";
  if (score >= 5) return "text-amber-300";
  return "text-rose-400";
}

function actionBadge(action) {
  if (["BUY NOW", "PREPARE ENTRY", "WAIT FOR CONFIRMATION"].includes(action)) {
    return "bg-emerald-500/15 text-emerald-300 border-emerald-500/30";
  }
  if (["WATCH", "KEEP ON WATCH"].includes(action)) {
    return "bg-amber-500/15 text-amber-300 border-amber-500/30";
  }
  return "bg-rose-500/15 text-rose-300 border-rose-500/30";
}

function riskBadge(risk) {
  if (risk === "High") return "bg-rose-500/15 text-rose-300 border-rose-500/30";
  if (risk === "Medium") return "bg-amber-500/15 text-amber-300 border-amber-500/30";
  return "bg-emerald-500/15 text-emerald-300 border-emerald-500/30";
}

function getDefaultDataUrl() {
  return `${import.meta.env.BASE_URL}data/dashboard-current.json`;
}

function StatCard({ icon: Icon, label, value }) {
  return (
    <div className="rounded-3xl border border-slate-800 bg-slate-900/70 p-4">
      <div className="flex items-center gap-2 text-slate-400 text-sm">
        <Icon className="w-4 h-4" />
        {label}
      </div>
      <div className="text-slate-50 text-2xl font-semibold mt-2">{value}</div>
    </div>
  );
}

function ActionLine({ title, body }) {
  return (
    <div>
      <div className="text-slate-400 text-xs uppercase tracking-wide mb-1">{title}</div>
      <div>{body}</div>
    </div>
  );
}

function Meter({ label, value, inverse = false }) {
  const normalized = Math.max(0, Math.min(100, value));
  return (
    <div>
      <div className="flex justify-between text-xs text-slate-400 mb-2">
        <span>{label}</span>
        <span>{Math.round(normalized)}</span>
      </div>
      <Progress value={inverse ? 100 - normalized : normalized} className="h-2 bg-slate-800" />
    </div>
  );
}

function MiniMetric({ icon: Icon, label, value }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
      <div className="flex items-center gap-2 text-slate-400 text-xs uppercase tracking-wide">
        <Icon className="w-4 h-4" />
        {label}
      </div>
      <div className="text-slate-50 text-2xl font-semibold mt-2">{value}</div>
    </div>
  );
}

function StatusPill({ status, text }) {
  const tone =
    status === "ok"
      ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
      : status === "warn"
      ? "bg-amber-500/15 text-amber-300 border-amber-500/30"
      : "bg-slate-700/50 text-slate-300 border-slate-700";

  return <Badge className={`rounded-xl ${tone}`}>{text}</Badge>;
}

function FunnelCard({ label, value, tone = "slate" }) {
  const toneMap = {
    emerald: "text-emerald-300 border-emerald-500/20 bg-emerald-500/5",
    amber: "text-amber-300 border-amber-500/20 bg-amber-500/5",
    rose: "text-rose-300 border-rose-500/20 bg-rose-500/5",
    slate: "text-slate-100 border-slate-800 bg-slate-900/70",
  };

  return (
    <div className={`rounded-2xl border p-4 ${toneMap[tone] || toneMap.slate}`}>
      <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
      <div className="mt-2 text-3xl font-semibold">{value}</div>
    </div>
  );
}

function RejectReasonCard({ label, value }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
      <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-rose-300">{value}</div>
    </div>
  );
}

function classifyQualityBand(item) {
  const score = Number(item?.score || 0);
  const impact = Number(item?.impactPct || 0);
  const risk = item?.risk || "High";
  const tradeUsd = Number(item?.tradeUsd || 0);

  if (score >= 8.8 && impact >= 1.0 && tradeUsd >= 30_000_000) return "Sniper";
  if (score >= 7.2 && risk !== "High") return "Balanced";
  return "Speculative";
}

function qualityBadge(quality) {
  if (quality === "Sniper") return "bg-emerald-500/15 text-emerald-300 border-emerald-500/30";
  if (quality === "Balanced") return "bg-cyan-500/15 text-cyan-300 border-cyan-500/30";
  return "bg-violet-500/15 text-violet-300 border-violet-500/30";
}

function TokenCard({ item, onOpen }) {
  const quality = classifyQualityBand(item);

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <Card className="bg-slate-950/70 border-slate-800 rounded-3xl shadow-2xl backdrop-blur">
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-3 flex-wrap">
            <div>
              <CardTitle className="text-slate-50 text-xl">{item.token}</CardTitle>
              <CardDescription className="text-slate-400 mt-1">{item.pair}</CardDescription>
            </div>
            <div className="flex gap-2 flex-wrap justify-end">
              <Badge className={qualityBadge(quality)}>{quality}</Badge>
              <Badge className={actionBadge(item.actionShort || item.action)}>
                {item.actionShort || item.action}
              </Badge>
            </div>
          </div>
        </CardHeader>

        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-3">
              <div className="text-slate-400">Score</div>
              <div className={`text-2xl font-semibold ${scoreColor(item.score)}`}>{item.score}</div>
            </div>
            <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-3">
              <div className="text-slate-400">Risk</div>
              <div className="mt-1">
                <Badge className={riskBadge(item.risk)}>{item.risk}</Badge>
              </div>
            </div>
          </div>

          <div>
            <div className="flex justify-between text-xs text-slate-400 mb-2">
              <span>Signal Strength</span>
              <span>{Math.min(100, Math.round((item.score || 0) * 10))}/100</span>
            </div>
            <Progress value={Math.min(100, Math.round((item.score || 0) * 10))} className="h-2 bg-slate-800" />
          </div>

          <div className="text-sm text-slate-300 leading-6">{item.why}</div>

          <div className="grid grid-cols-2 gap-3 text-sm text-slate-300">
            <div className="rounded-2xl bg-slate-900/60 border border-slate-800 p-3">
              <div className="text-slate-400 text-xs">Trade USD</div>
              <div className="font-medium">{fmtUsd(item.tradeUsd)}</div>
            </div>
            <div className="rounded-2xl bg-slate-900/60 border border-slate-800 p-3">
              <div className="text-slate-400 text-xs">Impact</div>
              <div className="font-medium">{item.impactPct}%</div>
            </div>
          </div>

          <div className="flex gap-2 pt-1">
            <Button className="rounded-2xl bg-slate-100 text-slate-950 hover:bg-white" onClick={() => onOpen(item)}>
              <Eye className="w-4 h-4 mr-2" />
              Open Detail
            </Button>
            <Button variant="outline" className="rounded-2xl border-slate-700 text-slate-200 hover:bg-slate-900">
              <Bell className="w-4 h-4 mr-2" />
              Set Alert
            </Button>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}

function SectionGrid({ title, desc, items, onOpen }) {
  return (
    <div className="space-y-4">
      <Card className="bg-slate-950/70 border-slate-800 rounded-3xl shadow-2xl">
        <CardHeader>
          <CardTitle className="text-slate-100">{title}</CardTitle>
          <CardDescription className="text-slate-400">{desc}</CardDescription>
        </CardHeader>
      </Card>

      {items.length === 0 ? (
        <Card className="bg-slate-950/70 border-slate-800 rounded-3xl shadow-2xl">
          <CardContent className="p-8 text-slate-400">No clean setup in this section right now.</CardContent>
        </Card>
      ) : (
        <div className="grid md:grid-cols-2 gap-4">
          {items.map((item) => (
            <TokenCard key={`${item.token}-${item.pair}`} item={item} onOpen={onOpen} />
          ))}
        </div>
      )}
    </div>
  );
}

function DetailPanel({ item }) {
  if (!item) {
    return (
      <Card className="bg-slate-950/70 border-slate-800 rounded-3xl shadow-2xl h-full">
        <CardContent className="p-8 text-slate-400 flex items-center justify-center h-full min-h-[420px]">
          Select a token card to view the full action plan.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-slate-950/70 border-slate-800 rounded-3xl shadow-2xl overflow-hidden">
      <CardHeader className="border-b border-slate-800 bg-gradient-to-r from-slate-950 to-slate-900">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div>
            <CardTitle className="text-slate-50 text-2xl">{item.token}</CardTitle>
            <CardDescription className="text-slate-400 mt-1">
              {item.pair} · {item.direction}
            </CardDescription>
          </div>
          <div className="flex gap-2 flex-wrap">
            <Badge className={actionBadge(item.actionShort || item.action)}>
              {item.actionShort || item.action}
            </Badge>
            <Badge className={riskBadge(item.risk)}>{item.risk}</Badge>
            <Badge className={qualityBadge(classifyQualityBand(item))}>{classifyQualityBand(item)}</Badge>
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-6 space-y-6">
        <div className="grid md:grid-cols-3 gap-4">
          <StatCard icon={Gauge} label="Action Score" value={String(item.score)} />
          <StatCard icon={Activity} label="Liquidity Impact" value={`${item.impactPct}%`} />
          <StatCard icon={Wallet} label="Trade Value" value={fmtUsd(item.tradeUsd)} />
        </div>

        <div className="grid lg:grid-cols-2 gap-6">
          <Card className="bg-slate-900/70 border-slate-800 rounded-3xl">
            <CardHeader>
              <CardTitle className="text-base text-slate-100">Next Practical Action</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm text-slate-300 leading-6">
              <ActionLine title="Action Now" body={item.action} />
              <ActionLine title="What it means" body={item.why} />
              <ActionLine title="What to do next" body={item.nextStep} />
              <ActionLine title="Do not do" body={item.doNot} />
              <ActionLine title="Cancel plan if" body={item.cancelIf} />
            </CardContent>
          </Card>

          <Card className="bg-slate-900/70 border-slate-800 rounded-3xl">
            <CardHeader>
              <CardTitle className="text-base text-slate-100">Signal Meter</CardTitle>
              <CardDescription className="text-slate-400">
                Momentum and confidence snapshot
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Meter label="Setup Quality" value={Math.min(100, (item.score || 0) * 10)} />
              <Meter
                label="Conviction"
                value={item.confidence === "High" ? 84 : item.confidence === "Medium" ? 66 : 38}
              />
              <Meter
                label="Risk Control"
                value={item.risk === "High" ? 35 : item.risk === "Medium" ? 62 : 84}
                inverse
              />
            </CardContent>
          </Card>
        </div>

        {item.history && Array.isArray(item.history) && item.history.length > 0 && (
          <Card className="bg-slate-900/70 border-slate-800 rounded-3xl">
            <CardHeader>
              <CardTitle className="text-base text-slate-100">Recent Performance Matrix</CardTitle>
              <CardDescription className="text-slate-400">
                Signal score trend for this token
              </CardDescription>
            </CardHeader>
            <CardContent className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={item.history}>
                  <defs>
                    <linearGradient id="grad1" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#22c55e" stopOpacity={0.5} />
                      <stop offset="100%" stopColor="#22c55e" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
                  <XAxis dataKey="d" stroke="#94a3b8" />
                  <YAxis stroke="#94a3b8" />
                  <Tooltip contentStyle={{ background: "#020617", border: "1px solid #334155", borderRadius: 16 }} />
                  <Area type="monotone" dataKey="score" stroke="#22c55e" fill="url(#grad1)" strokeWidth={3} />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        )}
      </CardContent>
    </Card>
  );
}

function PotentialTokenTable({ items, onPromote }) {
  return (
    <Card className="bg-slate-950/70 border-slate-800 rounded-3xl shadow-2xl">
      <CardHeader>
        <CardTitle className="text-slate-100">Potential Tokens</CardTitle>
        <CardDescription className="text-slate-400">
          Broader opportunities beyond the current qualified shortlist.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {items.length === 0 ? (
            <div className="text-slate-400">No potential tokens found right now.</div>
          ) : (
            items.map((item) => (
              <div key={item.token} className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
                <div className="flex items-start justify-between gap-3 flex-wrap">
                  <div>
                    <div className="text-slate-50 font-semibold text-lg">{item.token}</div>
                    <div className="text-slate-400 text-sm mt-1">{item.thesis}</div>
                  </div>
                  <Badge
                    className={
                      item.confidence === "Low"
                        ? "bg-rose-500/15 text-rose-300 border-rose-500/30"
                        : "bg-amber-500/15 text-amber-300 border-amber-500/30"
                    }
                  >
                    {item.confidence}
                  </Badge>
                </div>

                <div className="grid md:grid-cols-3 lg:grid-cols-6 gap-2 mt-4 text-sm">
                  <div className="rounded-xl bg-slate-950/60 px-3 py-2 border border-slate-800">
                    <span className="text-slate-400 block text-xs">Price</span>
                    <span className="text-slate-50">{item.price}</span>
                  </div>
                  <div className="rounded-xl bg-slate-950/60 px-3 py-2 border border-slate-800">
                    <span className="text-slate-400 block text-xs">FDV</span>
                    <span className="text-slate-50">{item.fdv}</span>
                  </div>
                  <div className="rounded-xl bg-slate-950/60 px-3 py-2 border border-slate-800">
                    <span className="text-slate-400 block text-xs">Liquidity</span>
                    <span className="text-slate-50">{item.liquidity}</span>
                  </div>
                  <div className="rounded-xl bg-slate-950/60 px-3 py-2 border border-slate-800">
                    <span className="text-slate-400 block text-xs">24H Volume</span>
                    <span className="text-slate-50">{item.volume24h}</span>
                  </div>
                  <div className="rounded-xl bg-slate-950/60 px-3 py-2 border border-slate-800">
                    <span className="text-slate-400 block text-xs">Stage</span>
                    <span className="text-slate-50">{item.listingStage}</span>
                  </div>
                  <div className="rounded-xl bg-slate-950/60 px-3 py-2 border border-slate-800">
                    <span className="text-slate-400 block text-xs">Tradability</span>
                    <span className="text-slate-50">{item.exchange}</span>
                  </div>
                </div>

                <div className="mt-4">
                  <Button
                    variant="outline"
                    className="rounded-2xl border-slate-700 text-slate-200 hover:bg-slate-900"
                    onClick={() => onPromote?.(item)}
                  >
                    <Rocket className="w-4 h-4 mr-2" />
                    Mark as manual watch
                  </Button>
                </div>
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function PresaleWatchlist({ items }) {
  return (
    <Card className="bg-slate-950/70 border-slate-800 rounded-3xl shadow-2xl">
      <CardHeader>
        <CardTitle className="text-slate-100">Presale Watchlist</CardTitle>
        <CardDescription className="text-slate-400">
          Not guaranteed trusted. Use this as a structured watchlist with red-flag awareness.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {items.length === 0 ? (
            <div className="text-slate-400">No presale watchlist items right now.</div>
          ) : (
            items.map((item) => (
              <div key={item.project} className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
                <div className="flex items-start justify-between gap-3 flex-wrap">
                  <div>
                    <div className="text-slate-50 font-semibold">{item.project}</div>
                    <div className="text-slate-400 text-sm mt-1">
                      {item.stage} · {item.launchDate}
                    </div>
                  </div>
                  <Badge
                    className={
                      item.action === "High caution"
                        ? "bg-rose-500/15 text-rose-300 border-rose-500/30"
                        : "bg-amber-500/15 text-amber-300 border-amber-500/30"
                    }
                  >
                    {item.action}
                  </Badge>
                </div>

                <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-2 mt-4 text-sm">
                  <div className="rounded-xl bg-slate-950/60 px-3 py-2 border border-slate-800">
                    <span className="text-slate-400 block text-xs">Trust Score</span>
                    <span className="text-slate-50">{item.trustScore}/100</span>
                  </div>
                  <div className="rounded-xl bg-slate-950/60 px-3 py-2 border border-slate-800">
                    <span className="text-slate-400 block text-xs">Tokenomics</span>
                    <span className="text-slate-50">{item.tokenomicsScore}/100</span>
                  </div>
                  <div className="rounded-xl bg-slate-950/60 px-3 py-2 border border-slate-800">
                    <span className="text-slate-400 block text-xs">Vesting</span>
                    <span className="text-slate-50">{item.vesting}</span>
                  </div>
                  <div className="rounded-xl bg-slate-950/60 px-3 py-2 border border-slate-800">
                    <span className="text-slate-400 block text-xs">Audit</span>
                    <span className="text-slate-50">{item.audit}</span>
                  </div>
                </div>

                <div className="mt-3 text-sm text-slate-400">
                  Red flags: <span className="text-slate-200">{item.redFlags}</span>
                </div>
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function SniperPicks({ items, onOpen }) {
  return (
    <Card className="bg-slate-950/70 border-slate-800 rounded-3xl shadow-2xl">
      <CardHeader>
        <CardTitle className="text-slate-100 flex items-center gap-2">
          <Rocket className="w-5 h-5 text-emerald-400" />
          Top Sniper Picks
        </CardTitle>
        <CardDescription className="text-slate-400">
          Best current names combining score, impact, and practical opportunity.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <div className="text-slate-400">No sniper candidates right now.</div>
        ) : (
          <div className="grid md:grid-cols-3 gap-4">
            {items.map((item, idx) => (
              <button
                key={`${item.token}-${idx}`}
                onClick={() => onOpen(item)}
                className="text-left rounded-3xl border border-slate-800 bg-slate-900/70 p-5 hover:bg-slate-900 transition"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="text-slate-50 text-xl font-semibold">{item.token}</div>
                  <Badge className="bg-emerald-500/15 text-emerald-300 border-emerald-500/30">
                    #{idx + 1}
                  </Badge>
                </div>
                <div className="text-slate-400 text-sm mt-1">{item.pair}</div>
                <div className="mt-4 grid grid-cols-2 gap-3">
                  <div className="rounded-2xl border border-slate-800 bg-slate-950/50 p-3">
                    <div className="text-slate-400 text-xs">Score</div>
                    <div className={`mt-1 text-2xl font-semibold ${scoreColor(item.score)}`}>{item.score}</div>
                  </div>
                  <div className="rounded-2xl border border-slate-800 bg-slate-950/50 p-3">
                    <div className="text-slate-400 text-xs">Impact</div>
                    <div className="mt-1 text-2xl font-semibold text-slate-50">{item.impactPct}%</div>
                  </div>
                </div>
                <div className="mt-4 text-sm text-slate-300 leading-6">{item.why}</div>
              </button>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function MajorsMonitor({ items, onOpen }) {
  return (
    <Card className="bg-slate-950/70 border-slate-800 rounded-3xl shadow-2xl">
      <CardHeader>
        <CardTitle className="text-slate-100 flex items-center gap-2">
          <LineChart className="w-5 h-5 text-cyan-400" />
          Tradeable Majors
        </CardTitle>
        <CardDescription className="text-slate-400">
          Higher-liquidity names to monitor for cleaner execution and market tone.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <div className="text-slate-400">No major assets flagged right now.</div>
        ) : (
          <div className="space-y-3">
            {items.map((item) => (
              <button
                key={`${item.token}-major`}
                onClick={() => onOpen(item)}
                className="w-full text-left rounded-2xl border border-slate-800 bg-slate-900/70 p-4 hover:bg-slate-900 transition"
              >
                <div className="flex items-start justify-between gap-3 flex-wrap">
                  <div>
                    <div className="text-slate-50 font-medium">
                      {item.token} <span className="text-slate-500 font-normal">· {item.pair}</span>
                    </div>
                    <div className="text-slate-400 text-sm mt-1">{item.direction}</div>
                  </div>
                  <Badge className={actionBadge(item.actionShort || item.action)}>{item.actionShort || item.action}</Badge>
                </div>
                <div className="mt-3 grid grid-cols-3 gap-2 text-sm">
                  <div className="rounded-xl bg-slate-950/60 px-3 py-2 border border-slate-800">Score <span className="text-slate-50 ml-1">{item.score}</span></div>
                  <div className="rounded-xl bg-slate-950/60 px-3 py-2 border border-slate-800">Impact <span className="text-slate-50 ml-1">{item.impactPct}%</span></div>
                  <div className="rounded-xl bg-slate-950/60 px-3 py-2 border border-slate-800">USD <span className="text-slate-50 ml-1">{fmtUsd(item.tradeUsd)}</span></div>
                </div>
              </button>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function RejectReasonsPanel({ rejectReasons = {} }) {
  const entries = Object.entries(rejectReasons || {}).filter(([, v]) => Number(v) > 0);

  return (
    <Card className="bg-slate-950/70 border-slate-800 rounded-3xl shadow-2xl">
      <CardHeader>
        <CardTitle className="text-slate-100 flex items-center gap-2">
          <ShieldAlert className="w-5 h-5 text-rose-400" />
          Reject Reasons
        </CardTitle>
        <CardDescription className="text-slate-400">
          Why the engine filtered names out before showing them.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {entries.length === 0 ? (
          <div className="text-slate-400">No reject data available.</div>
        ) : (
          <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-3">
            {entries.map(([label, value]) => (
              <RejectReasonCard
                key={label}
                label={label.replaceAll("_", " ")}
                value={value}
              />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function SnitchDashboardApp() {
  const [data, setData] = useState(starterData);
  const [selected, setSelected] = useState(null);
  const [search, setSearch] = useState("");
  const [minScore, setMinScore] = useState("0");
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [dataUrl, setDataUrl] = useState(getDefaultDataUrl());
  const [fetchState, setFetchState] = useState("idle");
  const [fetchMessage, setFetchMessage] = useState("Using starter data");
  const [showSourceTools, setShowSourceTools] = useState(false);
  const [manualWatch, setManualWatch] = useState([]);
  const fileRef = useRef(null);

  const loadParsedData = (parsed, sourceLabel = "Loaded data") => {
    const normalized = normalizeIncomingData(parsed);
    setData(normalized);
    setSelected(
      normalized.tradeFocusNow?.[0] ??
        normalized.emergingPotential?.[0] ??
        normalized.cautionAvoid?.[0] ??
        null
    );
    setFetchMessage(sourceLabel);
  };

  const fetchRemoteData = async () => {
    if (!dataUrl) return;
    try {
      setFetchState("loading");
      const res = await fetch(dataUrl, { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const parsed = await res.json();
      loadParsedData(parsed, `Connected to ${dataUrl}`);
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
    const id = setInterval(fetchRemoteData, 30000);
    return () => clearInterval(id);
  }, [autoRefresh, dataUrl]);

  const formatRelativeUpdate = (asOf) => {
    if (!asOf) return "Update time unavailable";
    if (String(asOf).includes("Bootstrapped")) return `Last sync: ${asOf}`;
    const parsed = new Date(String(asOf).replace(" UTC", "Z"));
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
      ...(data.cautionAvoid || []),
    ];

    return merged.filter((x) => {
      const scoreOk = Number(x.score || 0) >= Number(minScore || 0);
      const text = `${x.token} ${x.pair} ${x.direction} ${x.action}`.toLowerCase();
      const searchOk = !search || text.includes(search.toLowerCase());
      return scoreOk && searchOk;
    });
  }, [data, search, minScore]);

  const majorsList = useMemo(() => {
    return [...allCards]
      .filter((x) => x.isMajor)
      .sort((a, b) => Number(b.score || 0) - Number(a.score || 0))
      .slice(0, 8);
  }, [allCards]);

  const sniperPicks = useMemo(() => {
    return [...allCards]
      .filter((x) => !x.isMajor && Number(x.score || 0) >= 8.5 && Number(x.impactPct || 0) >= 1)
      .sort((a, b) => {
        const aRank = Number(a.score || 0) * 1000 + Number(a.impactPct || 0) * 100 + Math.log10(Math.max(1, Number(a.tradeUsd || 1)));
        const bRank = Number(b.score || 0) * 1000 + Number(b.impactPct || 0) * 100 + Math.log10(Math.max(1, Number(b.tradeUsd || 1)));
        return bRank - aRank;
      })
      .slice(0, 4);
  }, [allCards]);

  const perfBars = data.performance.scoreTrend || [];
  const pieData = data.performance.actionMix || [];
  const COLORS = ["#22c55e", "#f59e0b", "#ef4444"];
  const funnel = data.marketFunnel || starterData.marketFunnel;

  const loadJson = async (file) => {
    const text = await file.text();
    const parsed = JSON.parse(text);
    loadParsedData(parsed, `Loaded file: ${file.name}`);
    setFetchState("ok");
  };

  const promotePotentialToken = (token) => {
    setManualWatch((prev) => {
      if (prev.find((x) => x.token === token.token)) return prev;
      return [token, ...prev].slice(0, 6);
    });
  };

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(34,197,94,0.12),_transparent_28%),radial-gradient(circle_at_top_right,_rgba(59,130,246,0.12),_transparent_24%),linear-gradient(180deg,#020617_0%,#0f172a_100%)] text-slate-100">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="mb-6">
          <div className="flex flex-col xl:flex-row xl:items-center xl:justify-between gap-4">
            <div>
              <div className="flex items-center gap-3 flex-wrap">
                <div className="w-11 h-11 rounded-2xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center">
                  <Radar className="w-6 h-6 text-emerald-300" />
                </div>
                <div>
                  <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight">SNITCH Alert Dashboard</h1>
                  <p className="text-slate-400 mt-1">Dark premium signal workspace for fast trading decisions</p>
                </div>
              </div>
            </div>

            <div className="flex flex-wrap gap-2 items-center">
              <Badge className="rounded-xl bg-slate-900/80 border border-slate-700 text-slate-200">
                <Clock3 className="w-3.5 h-3.5 mr-1" />
                {formatRelativeUpdate(data.meta.asOf)}
              </Badge>
              <Badge className="rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-300">
                {data.meta.marketBias}
              </Badge>
              <StatusPill
                status={fetchState === "ok" ? "ok" : fetchState === "warn" ? "warn" : "idle"}
                text={fetchState === "ok" ? "Live data" : fetchState === "warn" ? "Fallback data" : "Starter data"}
              />
              <StatusPill status={autoRefresh ? "ok" : "idle"} text={autoRefresh ? "Auto refresh on" : "Manual refresh"} />
            </div>
          </div>
        </motion.div>

        <div className="grid xl:grid-cols-[1.25fr_0.75fr] gap-6 mb-6">
          <Card className="bg-slate-950/70 border-slate-800 rounded-3xl shadow-2xl">
            <CardContent className="p-5 sm:p-6">
              <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">
                <MiniMetric icon={Activity} label="Qualified" value={data.metrics.qualifiedSignals} />
                <MiniMetric icon={Target} label="Focus" value={data.metrics.tradeFocus} />
                <MiniMetric icon={Rocket} label="Emerging" value={data.metrics.emerging} />
                <MiniMetric icon={TriangleAlert} label="Caution" value={data.metrics.caution} />
                <MiniMetric icon={Gauge} label="Avg Confidence" value={`${data.metrics.avgConfidence}%`} />
                <MiniMetric icon={TrendingUp} label="30D Win Rate" value={`${data.metrics.winRate30d}%`} />
              </div>
            </CardContent>
          </Card>

          <Card className="bg-slate-950/70 border-slate-800 rounded-3xl shadow-2xl">
            <CardContent className="p-5 sm:p-6 space-y-3">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 text-sm text-slate-300">
                  <Database className="w-4 h-4 text-slate-400" />
                  Data Source
                </div>
                <Button
                  variant="outline"
                  className="rounded-2xl border-slate-700 text-slate-200 hover:bg-slate-900"
                  onClick={() => setShowSourceTools((v) => !v)}
                >
                  {showSourceTools ? "Hide technical tools" : "Show technical tools"}
                </Button>
              </div>

              <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 text-sm text-slate-300">
                <div className="font-medium text-slate-100 mb-1">Current status</div>
                <div>{fetchMessage}</div>
              </div>

              {showSourceTools && (
                <>
                  <div className="flex gap-2">
                    <div className="relative flex-1">
                      <Link2 className="absolute left-3 top-3.5 w-4 h-4 text-slate-500" />
                      <Input
                        value={dataUrl}
                        onChange={(e) => setDataUrl(e.target.value)}
                        placeholder={getDefaultDataUrl()}
                        className="pl-9 rounded-2xl bg-slate-900 border-slate-800 text-slate-100"
                      />
                    </div>
                    <Button className="rounded-2xl bg-slate-100 text-slate-950 hover:bg-white" onClick={fetchRemoteData}>
                      Connect
                    </Button>
                  </div>

                  <div className="flex items-center justify-between gap-2 flex-wrap text-xs text-slate-400">
                    <div className="flex items-center gap-2">
                      {fetchState === "ok" ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      ) : (
                        <AlertCircle className="w-4 h-4 text-amber-400" />
                      )}
                      <span>{fetchMessage}</span>
                    </div>
                    <div className="flex gap-2 flex-wrap">
                      <Button
                        variant="outline"
                        className="rounded-2xl border-slate-700 text-slate-200 hover:bg-slate-900"
                        onClick={() => setAutoRefresh((v) => !v)}
                      >
                        <RefreshCw className={`w-4 h-4 mr-2 ${autoRefresh ? "animate-spin" : ""}`} />
                        {autoRefresh ? "Auto Refresh On" : "Auto Refresh Off"}
                      </Button>
                      <Button
                        variant="outline"
                        className="rounded-2xl border-slate-700 text-slate-200 hover:bg-slate-900"
                        onClick={() => fileRef.current?.click()}
                      >
                        <Upload className="w-4 h-4 mr-2" />
                        Load JSON
                      </Button>
                      <input
                        ref={fileRef}
                        type="file"
                        accept="application/json"
                        className="hidden"
                        onChange={(e) => e.target.files?.[0] && loadJson(e.target.files[0])}
                      />
                    </div>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="grid xl:grid-cols-[1.2fr_0.8fr] gap-6 mb-6">
          <Card className="bg-slate-950/70 border-slate-800 rounded-3xl shadow-2xl">
            <CardContent className="p-5 sm:p-6 flex flex-col sm:flex-row gap-3">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-3.5 w-4 h-4 text-slate-500" />
                <Input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search token, pair, action"
                  className="pl-9 rounded-2xl bg-slate-900 border-slate-800 text-slate-100"
                />
              </div>
              <Select value={minScore} onValueChange={setMinScore}>
                <SelectTrigger className="w-full sm:w-44 rounded-2xl bg-slate-900 border-slate-800 text-slate-100">
                  <Filter className="w-4 h-4 mr-2" />
                  <SelectValue placeholder="Min score" />
                </SelectTrigger>
                <SelectContent className="bg-slate-950 border-slate-800 text-slate-100">
                  <SelectItem value="0">Min score 0</SelectItem>
                  <SelectItem value="4">Min score 4</SelectItem>
                  <SelectItem value="5">Min score 5</SelectItem>
                  <SelectItem value="6">Min score 6</SelectItem>
                  <SelectItem value="7">Min score 7</SelectItem>
                </SelectContent>
              </Select>
            </CardContent>
          </Card>

          <Card className="bg-slate-950/70 border-slate-800 rounded-3xl shadow-2xl">
            <CardContent className="p-5 sm:p-6 text-sm text-slate-300 leading-6">
              <div className="font-medium text-slate-100 mb-1">How to use this</div>
              Focus means highest-priority setups to inspect now. Emerging means promising but not fully confirmed. Caution means avoid new exposure or reduce risk.
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-6 mb-6">
          <SniperPicks items={sniperPicks} onOpen={setSelected} />
        </div>

        {manualWatch.length > 0 && (
          <div className="grid gap-6 mb-6">
            <Card className="bg-slate-950/70 border-slate-800 rounded-3xl shadow-2xl">
              <CardHeader>
                <CardTitle className="text-slate-100 flex items-center gap-2">
                  <Coins className="w-5 h-5 text-amber-300" />
                  Manual Watchlist
                </CardTitle>
                <CardDescription className="text-slate-400">
                  Potential tokens you manually promoted for closer monitoring.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
                  {manualWatch.map((item) => (
                    <div key={item.token} className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
                      <div className="flex items-center justify-between gap-2">
                        <div className="text-slate-50 font-semibold">{item.token}</div>
                        <Badge className="bg-amber-500/15 text-amber-300 border-amber-500/30">{item.confidence}</Badge>
                      </div>
                      <div className="text-slate-400 text-sm mt-2">{item.thesis}</div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        <div className="grid lg:grid-cols-[1fr_1fr] gap-6 mb-6">
          <MajorsMonitor items={majorsList} onOpen={setSelected} />
          <RejectReasonsPanel rejectReasons={funnel.rejectReasons || {}} />
        </div>

        <div className="grid lg:grid-cols-[1.2fr_0.8fr] gap-6 mb-6">
          <Tabs defaultValue="focus" className="w-full">
            <TabsList className="w-full bg-slate-950/70 border border-slate-800 rounded-2xl p-1 grid grid-cols-3">
              <TabsTrigger value="focus" className="rounded-2xl">Trade Focus</TabsTrigger>
              <TabsTrigger value="emerging" className="rounded-2xl">Emerging</TabsTrigger>
              <TabsTrigger value="caution" className="rounded-2xl">Caution</TabsTrigger>
            </TabsList>
            <TabsContent value="focus" className="mt-4">
              <SectionGrid title="Trade Focus Now" desc="Highest priority names to monitor immediately." items={data.tradeFocusNow.filter((x) => allCards.includes(x))} onOpen={setSelected} />
            </TabsContent>
            <TabsContent value="emerging" className="mt-4">
              <SectionGrid title="Emerging Potential" desc="Early setups that still need confirmation." items={data.emergingPotential.filter((x) => allCards.includes(x))} onOpen={setSelected} />
            </TabsContent>
            <TabsContent value="caution" className="mt-4">
              <SectionGrid title="Caution / Avoid" desc="Risky or bearish structures that need caution." items={data.cautionAvoid.filter((x) => allCards.includes(x))} onOpen={setSelected} />
            </TabsContent>
          </Tabs>

          <DetailPanel item={selected} />
        </div>

        <div className="grid xl:grid-cols-[0.8fr_1.2fr] gap-6 mb-6">
          <Card className="bg-slate-950/70 border-slate-800 rounded-3xl shadow-2xl">
            <CardHeader>
              <CardTitle className="text-slate-100">Action Mix</CardTitle>
              <CardDescription className="text-slate-400">Distribution of current dashboard actions</CardDescription>
            </CardHeader>
            <CardContent className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={60} outerRadius={95} paddingAngle={3}>
                    {pieData.map((entry, index) => (
                      <Cell key={entry.name} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ background: "#020617", border: "1px solid #334155", borderRadius: 16 }} />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <Card className="bg-slate-950/70 border-slate-800 rounded-3xl shadow-2xl">
            <CardHeader>
              <CardTitle className="text-slate-100">Performance Matrix</CardTitle>
              <CardDescription className="text-slate-400">Focus, emerging, and caution trend over recent sessions</CardDescription>
            </CardHeader>
            <CardContent className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={perfBars}>
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
            </CardContent>
          </Card>
        </div>

        <div className="grid xl:grid-cols-[0.9fr_1.1fr] gap-6 mb-6">
          <Card className="bg-slate-950/70 border-slate-800 rounded-3xl shadow-2xl">
            <CardHeader>
              <CardTitle className="text-slate-100">Proof Snapshot</CardTitle>
              <CardDescription className="text-slate-400">Quick performance metrics</CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-3">
              {(data.performance.proof || []).map((p) => (
                <div key={p.metric} className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
                  <div className="text-slate-400 text-xs">{p.metric}</div>
                  <div className="text-slate-50 text-2xl font-semibold mt-2">{p.value}</div>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card className="bg-slate-950/70 border-slate-800 rounded-3xl shadow-2xl">
            <CardHeader>
              <CardTitle className="text-slate-100">Recent Qualified Signals</CardTitle>
              <CardDescription className="text-slate-400">Latest filtered signals worth attention</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {(data.recentSignals || []).map((r) => (
                  <button
                    key={`${r.time}-${r.token}`}
                    onClick={() => {
                      const found = [...data.tradeFocusNow, ...data.emergingPotential, ...data.cautionAvoid].find((x) => x.token === r.token);
                      if (found) setSelected(found);
                    }}
                    className="w-full text-left rounded-2xl border border-slate-800 bg-slate-900/70 p-4 hover:bg-slate-900 transition"
                  >
                    <div className="flex items-start justify-between gap-3 flex-wrap">
                      <div>
                        <div className="text-slate-50 font-medium">
                          {r.token} <span className="text-slate-500 font-normal">· {r.pair}</span>
                        </div>
                        <div className="text-slate-400 text-sm mt-1">{r.direction}</div>
                      </div>
                      <div className="text-right">
                        <Badge className={actionBadge(r.action)}>{r.action}</Badge>
                        <div className="text-slate-400 text-xs mt-2">{r.time}</div>
                      </div>
                    </div>
                    <div className="mt-3 grid grid-cols-3 gap-2 text-sm">
                      <div className="rounded-xl bg-slate-950/60 px-3 py-2 border border-slate-800">Score <span className="text-slate-50 ml-1">{r.score}</span></div>
                      <div className="rounded-xl bg-slate-950/60 px-3 py-2 border border-slate-800">Impact <span className="text-slate-50 ml-1">{r.impact}</span></div>
                      <div className="rounded-xl bg-slate-950/60 px-3 py-2 border border-slate-800">USD <span className="text-slate-50 ml-1">{r.usd}</span></div>
                    </div>
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="grid lg:grid-cols-[0.9fr_1.1fr] gap-6 mb-6">
          <Card className="bg-slate-950/70 border-slate-800 rounded-3xl shadow-2xl">
            <CardHeader>
              <CardTitle className="text-slate-100">Scan Funnel</CardTitle>
              <CardDescription className="text-slate-400">See how much the engine scanned versus what survived filtering.</CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              <FunnelCard label="Scanned" value={funnel.scanned} tone="slate" />
              <FunnelCard label="Rejected" value={funnel.rejected} tone="rose" />
              <FunnelCard label="Qualified" value={funnel.qualified} tone="emerald" />
              <FunnelCard label="Displayed" value={funnel.displayed} tone="amber" />
            </CardContent>
          </Card>

          <Card className="bg-slate-950/70 border-slate-800 rounded-3xl shadow-2xl">
            <CardHeader>
              <CardTitle className="text-slate-100">Tradability Confidence</CardTitle>
              <CardDescription className="text-slate-400">
                Use this to separate early ideas from names you can trade with more confidence.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 text-sm text-slate-300">
              <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
                <div className="text-slate-100 font-medium mb-2">Trade with more confidence</div>
                <div className="text-slate-400">Listed or watchable on major venues, enough liquidity, and better execution conditions.</div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {[...data.tradeFocusNow, ...data.emergingPotential]
                    .filter((x) => x.binanceTradable)
                    .map((x) => (
                      <Badge key={x.token} className="bg-emerald-500/15 text-emerald-300 border-emerald-500/30">
                        {x.token}
                      </Badge>
                    ))}
                </div>
              </div>

              <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
                <div className="text-slate-100 font-medium mb-2">Watch but size carefully</div>
                <div className="text-slate-400">Potential exists, but venue/liquidity/risk means smaller size or slower confirmation.</div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {[...data.emergingPotential, ...data.cautionAvoid]
                    .filter((x) => !x.binanceTradable)
                    .map((x) => (
                      <Badge key={x.token} className="bg-amber-500/15 text-amber-300 border-amber-500/30">
                        {x.token}
                      </Badge>
                    ))}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="grid lg:grid-cols-2 gap-6">
          <PotentialTokenTable items={data.potentialTokens || []} onPromote={promotePotentialToken} />
          <PresaleWatchlist items={data.presaleWatchlist || []} />
        </div>
      </div>
    </div>
  );
}
