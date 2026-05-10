import { AnimatePresence, motion } from "framer-motion";
import { InvestigationGraph } from "@/components/InvestigationGraph";
import {
  Activity,
  Bell,
  BrainCircuit,
  ChevronRight,
  Command,
  Database,
  FileScan,
  Fingerprint,
  Gauge,
  LayoutDashboard,
  Map,
  Radar,
  Search,
  Settings,
  ShieldAlert,
  Siren,
  Sparkles,
  UploadCloud,
  UserCircle2,
  Trash2
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  PolarAngleAxis,
  PolarGrid,
  Radar as RadarChartShape,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { analyzeCase, createCase, deleteCase, getAnalysisResults, getCases, getReport, getReportDocumentUrl, uploadEvidence } from "@/lib/api";
import { activityData, confidenceData, mockCases, mockReport, mockTimeline, riskData } from "@/lib/mock-data";
import type { CaseRecord, CaseReport } from "@/lib/types";
import { cn, delay, formatDate } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";

const navItems = [
  { label: "Dashboard", icon: LayoutDashboard },
  { label: "Case Details", icon: FileScan },
  { label: "Narrative Graph", icon: Map },
  { label: "Evidence", icon: Database },
  { label: "AI Analysis", icon: BrainCircuit },
  { label: "Risk Engine", icon: ShieldAlert },
  { label: "Settings", icon: Settings }
];

const evidenceTypes = [
  { key: "autopsy", label: "Autopsy report", icon: Fingerprint, accept: ".pdf" },
  { key: "cctv", label: "CCTV logs", icon: Radar, accept: ".csv,.txt,.log" },
  { key: "metadata", label: "Metadata", icon: Database, accept: ".json,.csv,.txt" },
  { key: "image", label: "Images", icon: FileScan, accept: ".jpg,.jpeg,.png" },
  { key: "gps", label: "GPS records", icon: Map, accept: ".csv,.txt,.log" }
];

const processLogs = [
  "Parsing autopsy report...",
  "Extracting injury signatures...",
  "Correlating CCTV and GPS metadata...",
  "Building timeline reconstruction...",
  "Detecting anomalies and route conflicts...",
  "Generating forensic intelligence story...",
  "Preparing police investigation briefing..."
];

type FlowStep = "case" | "upload" | "analysis" | "results";

type CaseForm = {
  title: string;
  victim_name: string;
  incident_location: string;
  incident_date: string;
  notes: string;
  priority: string;
};

export default function App() {
  const [intro, setIntro] = useState(true);
  const [cases, setCases] = useState<CaseRecord[]>(mockCases);
  const [selectedCase, setSelectedCase] = useState<CaseReport>(mockReport);
  const [flowOpen, setFlowOpen] = useState(false);
  const [flowStep, setFlowStep] = useState<FlowStep>("case");
  const [liveLogs, setLiveLogs] = useState<string[]>([]);
  const [analysisProgress, setAnalysisProgress] = useState(0);
  const [activeTab, setActiveTab] = useState("Dashboard");

  useEffect(() => {
    const timer = window.setTimeout(() => setIntro(false), 2400);
    refreshCases();
    return () => window.clearTimeout(timer);
  }, []);

  async function refreshCases() {
    const items = await getCases();
    if (items.length) setCases(items);
  }

  async function handleDeleteCase(id: string) {
    if (!confirm("Are you sure you want to delete this case? This action cannot be undone.")) return;
    try {
      await deleteCase(id);
      await refreshCases();
      if (selectedCase?.case_id === id) {
        setSelectedCase(mockReport);
        setActiveTab("Dashboard");
      }
    } catch (e) {
      console.error("Failed to delete case", e);
      alert("Failed to delete case.");
    }
  }

  const intelligence = selectedCase?.structured_report?.investigative_intelligence || selectedCase?.investigative_intelligence;
  const timeline = selectedCase?.structured_report?.timeline_analysis?.events || selectedCase?.timeline || mockTimeline;
  const riskScore = selectedCase?.structured_report?.risk_assessment?.risk_score || selectedCase?.risk_score || 0;
  const confidenceRows = useMemo(
    () =>
      confidenceData.map((row) => ({
        ...row,
        score: row.name === "Risk" ? Math.max(row.score, riskScore) : row.score
      })),
    [riskScore]
  );

  async function loadCase(caseId: string) {
    try {
      const report = await getReport(caseId);
      setSelectedCase(report);
    } catch (error) {
      console.error("Failed to load case report", error);
      alert("This case has no completed report yet. Run analysis first.");
    }
  }

  return (
    <div className="min-h-screen overflow-hidden bg-radial-grid text-foreground">
      <BackgroundFX />
      <AnimatePresence>{intro ? <IntroScanner /> : null}</AnimatePresence>
      <div className="relative z-10 flex min-h-screen">
        <Sidebar activeTab={activeTab} onTabSelect={setActiveTab} />
        <main className="min-w-0 flex-1 px-4 py-4 md:px-6 lg:px-8">
          <Topbar onCreate={() => setFlowOpen(true)} />
          <motion.section
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7 }}
            className="mt-6"
          >
            {activeTab === "Dashboard" ? (
              <>
                <HeroCommand selectedCase={selectedCase} onCreate={() => setFlowOpen(true)} />
                <MetricGrid cases={cases} />
                <div className="mt-6 grid gap-6 2xl:grid-cols-[1.15fr_.85fr]">
                  <CommandAnalytics riskScore={riskScore} confidenceRows={confidenceRows} />
                  <HeatmapPanel />
                </div>
                <div className="mt-6">
                  <CasesPanel 
                    cases={cases} 
                    selected={selectedCase?.case_id} 
                    onSelect={(id) => { loadCase(id); setActiveTab("Case Details"); }} 
                    onDelete={handleDeleteCase}
                  />
                </div>
              </>
            ) : activeTab === "Case Details" ? (
              <div className="space-y-6">
                <HeroCommand selectedCase={selectedCase} onCreate={() => setFlowOpen(true)} />
                <div className="grid gap-6 2xl:grid-cols-[1.15fr_.85fr]">
                  <CaseIntelPanel report={selectedCase} intelligence={intelligence} onOpenReport={() => window.open(getReportDocumentUrl(selectedCase.case_id), "_blank")} />
                  <CorrelationNetwork />
                </div>
                <TimelinePanel timeline={timeline} />
              </div>
            ) : activeTab === "Narrative Graph" ? (
              <InvestigationGraph caseId={selectedCase.case_id} />
            ) : (
              <div className="flex h-[60vh] flex-col items-center justify-center rounded-3xl border border-white/10 bg-slate-950/40 text-center">
                <BrainCircuit className="h-16 w-16 text-cyan-500/50" />
                <h3 className="mt-4 text-2xl font-bold text-white">{activeTab}</h3>
                <p className="mt-2 text-slate-400">This module is part of the advanced forensic suite.</p>
                <Button className="mt-6" onClick={() => setActiveTab("Dashboard")}>Return to Dashboard</Button>
              </div>
            )}
          </motion.section>
        </main>
      </div>

      <CaseFlowDialog
        open={flowOpen}
        step={flowStep}
        setStep={setFlowStep}
        logs={liveLogs}
        progress={analysisProgress}
        onClose={() => {
          setFlowOpen(false);
          setFlowStep("case");
          setLiveLogs([]);
          setAnalysisProgress(0);
        }}
        onComplete={(report, created) => {
          setSelectedCase(report);
          setCases((prev) => [created, ...prev.filter((item) => item.case_id !== created.case_id)]);
        }}
        runLogs={async () => {
          setLiveLogs([]);
          setAnalysisProgress(0);
          for (let i = 0; i < processLogs.length; i += 1) {
            await delay(520);
            setLiveLogs((prev) => [...prev, processLogs[i]]);
            setAnalysisProgress(Math.round(((i + 1) / processLogs.length) * 100));
          }
        }}
      />
    </div>
  );
}

function BackgroundFX() {
  return (
    <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden">
      <div className="grid-overlay absolute inset-0 opacity-60" />
      {Array.from({ length: 24 }).map((_, index) => (
        <motion.span
          key={index}
          className="absolute h-1 w-1 rounded-full bg-cyan-300/70 shadow-[0_0_18px_rgba(34,211,238,.9)]"
          style={{ left: `${(index * 37) % 100}%`, top: `${(index * 19) % 100}%` }}
          animate={{ y: [0, -22, 0], opacity: [0.25, 1, 0.25] }}
          transition={{ duration: 4 + (index % 5), repeat: Infinity, delay: index * 0.13 }}
        />
      ))}
      <div className="absolute -left-28 top-20 h-80 w-80 rounded-full bg-cyan-400/15 blur-3xl" />
      <div className="absolute right-0 top-1/4 h-96 w-96 rounded-full bg-violet-500/15 blur-3xl" />
      <div className="absolute bottom-0 left-1/3 h-72 w-72 rounded-full bg-blue-500/10 blur-3xl" />
    </div>
  );
}

function IntroScanner() {
  return (
    <motion.div
      className="fixed inset-0 z-50 grid place-items-center bg-[#050814]"
      exit={{ opacity: 0, scale: 1.04 }}
      transition={{ duration: 0.7 }}
    >
      <div className="scanline relative flex h-72 w-[min(92vw,560px)] flex-col items-center justify-center overflow-hidden rounded-3xl border border-cyan-300/25 bg-slate-950/70 shadow-[0_0_80px_rgba(34,211,238,.16)]">
        <motion.div
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.8 }}
          className="grid h-20 w-20 place-items-center rounded-3xl border border-cyan-300/30 bg-cyan-300/10"
        >
          <Fingerprint className="h-10 w-10 text-cyan-200" />
        </motion.div>
        <motion.h1
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35 }}
          className="mt-6 text-4xl font-black tracking-[0.18em] text-white"
        >
          ForensiAI
        </motion.h1>
        <TypingLine text="AI-Powered Forensic Intelligence Platform" />
      </div>
    </motion.div>
  );
}

function TypingLine({ text }: { text: string }) {
  const [shown, setShown] = useState("");
  useEffect(() => {
    let i = 0;
    const timer = window.setInterval(() => {
      i += 1;
      setShown(text.slice(0, i));
      if (i >= text.length) window.clearInterval(timer);
    }, 38);
    return () => window.clearInterval(timer);
  }, [text]);
  return <p className="mt-3 min-h-6 text-sm tracking-[0.2em] text-cyan-200">{shown}<span className="animate-pulse">|</span></p>;
}

function Sidebar({ activeTab, onTabSelect }: { activeTab: string; onTabSelect: (tab: string) => void }) {
  return (
    <aside className="hidden w-72 shrink-0 border-r border-white/10 bg-slate-950/35 p-5 backdrop-blur-2xl lg:block">
      <div className="flex items-center gap-3">
        <div className="grid h-12 w-12 place-items-center rounded-2xl bg-cyan-300/10 ring-1 ring-cyan-300/30">
          <Command className="h-6 w-6 text-cyan-200" />
        </div>
        <div>
          <p className="text-lg font-black tracking-wide text-white">ForensiAI</p>
          <p className="text-xs text-slate-400">Command Center</p>
        </div>
      </div>
      <nav className="mt-9 space-y-2">
        {navItems.map((item, index) => (
          <motion.button
            key={item.label}
            onClick={() => onTabSelect(item.label)}
            initial={{ opacity: 0, x: -14 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.06 * index }}
            className={cn(
              "flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-sm font-semibold text-slate-300 transition hover:bg-cyan-300/10 hover:text-white",
              activeTab === item.label && "bg-cyan-300/12 text-cyan-100 ring-1 ring-cyan-300/20"
            )}
          >
            <item.icon className="h-5 w-5" />
            {item.label}
          </motion.button>
        ))}
      </nav>
      <div className="mt-8 rounded-3xl border border-cyan-300/15 bg-cyan-300/8 p-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-cyan-100">
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-400 shadow-[0_0_16px_rgba(52,211,153,.9)]" />
          System Online
        </div>
        <p className="mt-3 text-xs leading-5 text-slate-400">Backend connected. AI risk engine and report generator are ready for demo review.</p>
      </div>
    </aside>
  );
}

function Topbar({ onCreate }: { onCreate: () => void }) {
  return (
    <header className="glass sticky top-4 z-30 flex flex-col gap-3 rounded-3xl px-4 py-3 md:flex-row md:items-center md:justify-between">
      <div className="flex min-w-0 flex-1 items-center gap-3 rounded-2xl border border-white/10 bg-slate-950/40 px-3 py-2">
        <Search className="h-4 w-4 text-cyan-200" />
        <input className="min-w-0 flex-1 bg-transparent text-sm text-white outline-none placeholder:text-slate-500" placeholder="Search case ID, evidence, vehicle, location..." />
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <Badge tone="green" className="gap-2"><span className="h-2 w-2 rounded-full bg-emerald-300" /> Live AI Processing</Badge>
        <Button variant="secondary" className="h-10 w-10 px-0"><Bell className="h-4 w-4" /></Button>
        <div className="flex items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-3 py-2">
          <UserCircle2 className="h-5 w-5 text-cyan-200" />
          <span className="text-sm font-semibold">Investigator</span>
        </div>
        <Button onClick={onCreate}><Sparkles className="h-4 w-4" /> Create New Case</Button>
      </div>
    </header>
  );
}

function HeroCommand({ selectedCase, onCreate }: { selectedCase: CaseReport; onCreate: () => void }) {
  return (
    <Card className="relative overflow-hidden p-0">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_10%,rgba(34,211,238,.22),transparent_28%),radial-gradient(circle_at_80%_20%,rgba(139,92,246,.22),transparent_30%)]" />
      <div className="relative grid gap-6 p-6 lg:grid-cols-[1.35fr_.65fr] lg:p-8">
        <div>
          <Badge tone="cyan">Forensic Intelligence Operations</Badge>
          <h1 className="mt-5 max-w-4xl text-4xl font-black leading-tight text-white md:text-6xl">
            Real-time AI command center for high-risk investigations.
          </h1>
          <p className="mt-5 max-w-3xl text-base leading-7 text-slate-300">
            Track evidence, reconstruct timelines, surface anomalies, and convert forensic data into investigator-ready intelligence.
          </p>
          <div className="mt-7 flex flex-wrap gap-3">
            <Button onClick={onCreate}><UploadCloud className="h-4 w-4" /> Launch Investigation Flow</Button>
            <Button variant="secondary" onClick={() => window.open(getReportDocumentUrl(selectedCase.case_id), "_blank")}>
              Open Intelligence Report <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
        <div className="scanline relative min-h-72 overflow-hidden rounded-3xl border border-cyan-300/20 bg-slate-950/45 p-5">
          <div className="absolute inset-8 rounded-full border border-cyan-300/10" />
          <div className="absolute inset-14 rounded-full border border-violet-300/10" />
          <motion.div
            className="absolute left-1/2 top-1/2 h-36 w-36 -translate-x-1/2 -translate-y-1/2 rounded-full border border-cyan-300/30"
            animate={{ rotate: 360 }}
            transition={{ duration: 18, repeat: Infinity, ease: "linear" }}
          />
          <div className="relative z-10 flex h-full flex-col justify-between">
            <Badge tone="red">Risk {selectedCase.risk_score}/100</Badge>
            <div>
              <p className="text-sm text-slate-400">Active Case</p>
              <h2 className="mt-2 text-2xl font-bold text-white">{selectedCase.case_id}</h2>
              <p className="mt-2 text-sm text-slate-300">{selectedCase.victim_name} · {selectedCase.incident_location}</p>
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
}

function MetricGrid({ cases }: { cases: CaseRecord[] }) {
  const metrics = [
    { label: "Total Cases", value: cases.length || 24, icon: FileScan, color: "cyan" },
    { label: "Active Investigations", value: cases.filter((c) => c.status !== "completed").length || 8, icon: Activity, color: "violet" },
    { label: "High-Risk Cases", value: cases.filter((c) => c.risk_level === "HIGH").length || 6, icon: Siren, color: "red" },
    { label: "Evidence Processed", value: 148, icon: Database, color: "cyan" },
    { label: "AI Correlations", value: 37, icon: BrainCircuit, color: "violet" },
    { label: "Timelines Built", value: 19, icon: Map, color: "cyan" }
  ];
  return (
    <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
      {metrics.map((metric, index) => (
        <motion.div key={metric.label} initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.06 }}>
          <Card className="group overflow-hidden hover:-translate-y-1 hover:border-cyan-300/35">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <metric.icon className={cn("h-5 w-5", metric.color === "red" ? "text-rose-300" : metric.color === "violet" ? "text-violet-300" : "text-cyan-200")} />
                <MiniTrend />
              </div>
              <p className="mt-5 text-3xl font-black text-white">{metric.value}</p>
              <p className="mt-1 text-xs uppercase tracking-[0.16em] text-slate-400">{metric.label}</p>
            </CardContent>
          </Card>
        </motion.div>
      ))}
    </div>
  );
}

function MiniTrend() {
  return (
    <div className="h-8 w-16">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={activityData.slice(0, 5)}>
          <Area type="monotone" dataKey="ai" stroke="#22D3EE" fill="rgba(34,211,238,.18)" strokeWidth={2} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function CommandAnalytics({ riskScore, confidenceRows }: { riskScore: number; confidenceRows: Array<{ name: string; score: number }> }) {
  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <Card>
        <CardHeader><CardTitle>Investigation Activity</CardTitle></CardHeader>
        <CardContent className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={activityData}>
              <CartesianGrid stroke="rgba(148,163,184,.12)" vertical={false} />
              <XAxis dataKey="day" stroke="#94A3B8" />
              <YAxis stroke="#94A3B8" />
              <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid rgba(255,255,255,.12)", borderRadius: 14 }} />
              <Line type="monotone" dataKey="cases" stroke="#38BDF8" strokeWidth={3} dot={false} />
              <Line type="monotone" dataKey="ai" stroke="#8B5CF6" strokeWidth={3} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Risk Distribution</CardTitle></CardHeader>
        <CardContent className="grid h-72 place-items-center">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={riskData} dataKey="value" nameKey="name" innerRadius={62} outerRadius={94} paddingAngle={6}>
                {riskData.map((entry) => <Cell key={entry.name} fill={entry.fill} />)}
              </Pie>
              <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid rgba(255,255,255,.12)", borderRadius: 14 }} />
            </PieChart>
          </ResponsiveContainer>
          <div className="pointer-events-none absolute text-center">
            <p className="text-3xl font-black text-white">{Math.round(riskScore)}</p>
            <p className="text-xs text-slate-400">live risk</p>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>AI Confidence Scores</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          {confidenceRows.map((item) => (
            <div key={item.name}>
              <div className="mb-2 flex justify-between text-sm"><span>{item.name}</span><span className="text-cyan-200">{item.score}%</span></div>
              <Progress value={item.score} tone={item.name === "Risk" ? "red" : "cyan"} />
            </div>
          ))}
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Investigation Progress Tracker</CardTitle></CardHeader>
        <CardContent>
          {["Case opened", "Evidence parsed", "Timeline built", "Risk scored", "Report generated"].map((item, index) => (
            <div key={item} className="flex items-center gap-3 pb-4 last:pb-0">
              <div className="grid h-8 w-8 place-items-center rounded-full bg-cyan-300/15 text-xs font-bold text-cyan-100 ring-1 ring-cyan-300/25">{index + 1}</div>
              <div className="flex-1">
                <p className="text-sm font-semibold text-white">{item}</p>
                <Progress value={100} tone={index > 2 ? "violet" : "cyan"} />
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function CaseIntelPanel({ report, intelligence, onOpenReport }: { report: CaseReport; intelligence?: CaseReport["investigative_intelligence"]; onOpenReport: () => void }) {
  return (
    <Card className="overflow-hidden">
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div>
          <CardTitle>AI Investigation Insights</CardTitle>
          <p className="mt-2 text-sm text-slate-400">{report.case_id} · {report.victim_name}</p>
        </div>
        <Badge tone={report.risk_level === "HIGH" ? "red" : "yellow"}>{report.risk_level}</Badge>
      </CardHeader>
      <CardContent className="space-y-4">
        <InsightCard title="Crime Story" body={intelligence?.crime_story || report.summary || "No crime story generated yet."} icon={BrainCircuit} />
        <InsightCard title="Case Breakthrough" body={intelligence?.case_breakthrough || "Upload evidence and run analysis to generate a breakthrough hypothesis."} icon={Sparkles} accent />
        <div className="grid gap-3 sm:grid-cols-2">
          {(intelligence?.priority_leads || ["Pull CCTV overwrite-window footage", "Map route conflicts", "Check suspect injury trail"]).slice(0, 4).map((lead) => (
            <div key={lead} className="rounded-2xl border border-white/10 bg-white/[0.04] p-3 text-sm text-slate-300">{lead}</div>
          ))}
        </div>
        <Button variant="secondary" onClick={onOpenReport}>Open Full Report <ChevronRight className="h-4 w-4" /></Button>
      </CardContent>
    </Card>
  );
}

function InsightCard({ title, body, icon: Icon, accent }: { title: string; body: string; icon: typeof BrainCircuit; accent?: boolean }) {
  return (
    <div className={cn("rounded-2xl border p-4", accent ? "border-cyan-300/30 bg-cyan-300/10" : "border-white/10 bg-white/[0.04]")}>
      <div className="flex items-center gap-2 text-sm font-bold text-white"><Icon className="h-4 w-4 text-cyan-200" />{title}</div>
      <p className="mt-3 text-sm leading-6 text-slate-300">{body}</p>
    </div>
  );
}

function TimelinePanel({ timeline }: { timeline: CaseReport["timeline"] }) {
  const events = timeline || [];
  return (
    <Card>
      <CardHeader><CardTitle>Interactive Case Timeline</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        {events.map((event, index) => (
          <motion.div key={`${event.timestamp}-${index}`} initial={{ opacity: 0, x: -18 }} whileInView={{ opacity: 1, x: 0 }} className="relative border-l border-cyan-300/20 pl-5">
            <span className="absolute -left-2 top-1 h-4 w-4 rounded-full bg-cyan-300 shadow-[0_0_18px_rgba(34,211,238,.9)]" />
            <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={event.severity === "high" ? "red" : "cyan"}>{event.source}</Badge>
                <span className="text-sm text-slate-400">{formatDate(event.timestamp)}</span>
              </div>
              <p className="mt-2 text-sm text-white">{event.event}</p>
            </div>
          </motion.div>
        ))}
      </CardContent>
    </Card>
  );
}

function CorrelationNetwork() {
  const nodes = [
    { label: "Suspect", x: "50%", y: "16%" },
    { label: "Phone", x: "24%", y: "42%" },
    { label: "CCTV", x: "76%", y: "42%" },
    { label: "Location", x: "34%", y: "76%" },
    { label: "Vehicle", x: "66%", y: "76%" }
  ];
  return (
    <Card>
      <CardHeader><CardTitle>Evidence Correlation Network</CardTitle></CardHeader>
      <CardContent>
        <div className="relative h-[420px] overflow-hidden rounded-3xl border border-white/10 bg-slate-950/45">
          <svg className="absolute inset-0 h-full w-full">
            {[[0, 1], [0, 2], [1, 3], [2, 4], [3, 4], [1, 4]].map(([a, b], index) => (
              <motion.line
                key={`${a}-${b}`}
                x1={nodes[a].x}
                y1={nodes[a].y}
                x2={nodes[b].x}
                y2={nodes[b].y}
                stroke="rgba(34,211,238,.35)"
                strokeWidth="2"
                initial={{ pathLength: 0 }}
                animate={{ pathLength: 1 }}
                transition={{ duration: 1.2, delay: index * 0.15, repeat: Infinity, repeatType: "reverse", repeatDelay: 3 }}
              />
            ))}
          </svg>
          {nodes.map((node, index) => (
            <motion.div
              key={node.label}
              className="absolute grid h-24 w-24 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border border-cyan-300/30 bg-cyan-300/10 text-center text-xs font-bold text-cyan-100 shadow-glow"
              style={{ left: node.x, top: node.y }}
              animate={{ y: [0, -8, 0] }}
              transition={{ duration: 3, repeat: Infinity, delay: index * 0.25 }}
            >
              {node.label}
            </motion.div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function HeatmapPanel() {
  const cells = Array.from({ length: 49 }, (_, index) => (index * 17 + 31) % 100);
  return (
    <Card>
      <CardHeader><CardTitle>Suspicious Activity Heatmap</CardTitle></CardHeader>
      <CardContent>
        <div className="grid grid-cols-7 gap-2">
          {cells.map((value, index) => (
            <motion.div
              key={index}
              className="aspect-square rounded-xl border border-white/10"
              style={{ backgroundColor: value > 72 ? `rgba(251,59,100,${value / 120})` : `rgba(34,211,238,${value / 180})` }}
              whileHover={{ scale: 1.08 }}
            />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function CasesPanel({ cases, selected, onSelect, onDelete }: { cases: CaseRecord[]; selected: string; onSelect: (caseId: string) => void; onDelete: (caseId: string) => void }) {
  return (
    <Card>
      <CardHeader><CardTitle>Active Case Queue</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        {cases.slice(0, 6).map((item) => (
          <div key={item.case_id} className="flex gap-2">
            <button
              onClick={() => onSelect(item.case_id)}
              className={cn("flex flex-1 items-center justify-between rounded-2xl border p-4 text-left transition", selected === item.case_id ? "border-cyan-300/35 bg-cyan-300/10" : "border-white/10 bg-white/[0.04] hover:bg-white/[0.08]")}
            >
              <div>
                <p className="font-semibold text-white">{item.case_id}</p>
                <p className="mt-1 text-sm text-slate-400">{item.victim_name} · {item.incident_location}</p>
              </div>
              <Badge tone={item.risk_level === "HIGH" ? "red" : item.risk_level === "MEDIUM" ? "yellow" : "green"}>{item.risk_level}</Badge>
            </button>
            <button 
              onClick={(e) => { e.stopPropagation(); onDelete(item.case_id); }}
              className="flex items-center justify-center p-4 rounded-2xl border border-red-500/20 bg-red-500/10 text-red-400 hover:bg-red-500/20 hover:text-red-300 transition"
              title="Delete Case"
            >
              <Trash2 className="w-5 h-5" />
            </button>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function CaseFlowDialog({
  open,
  step,
  setStep,
  logs,
  progress,
  onClose,
  onComplete,
  runLogs
}: {
  open: boolean;
  step: FlowStep;
  setStep: (step: FlowStep) => void;
  logs: string[];
  progress: number;
  onClose: () => void;
  onComplete: (report: CaseReport, created: CaseRecord) => void;
  runLogs: () => Promise<void>;
}) {
  const [form, setForm] = useState<CaseForm>({
    title: "",
    victim_name: "",
    incident_location: "",
    incident_date: new Date().toISOString().slice(0, 10),
    notes: "",
    priority: "HIGH"
  });
  const [files, setFiles] = useState<Record<string, File | null>>({});
  const [uploadProgress, setUploadProgress] = useState<Record<string, number>>({});
  const [createdCase, setCreatedCase] = useState<CaseRecord | null>(null);
  const [busy, setBusy] = useState(false);

  async function createAndUpload() {
    setBusy(true);
    try {
      const created = await createCase({
        victim_name: form.victim_name || form.title || "Unknown victim",
        incident_location: form.incident_location || "Unknown location",
        incident_date: form.incident_date,
        notes: `${form.title ? `Case Title: ${form.title}\n` : ""}${form.notes}`
      });
      setCreatedCase(created);
      for (const item of evidenceTypes) {
        const file = files[item.key];
        if (!file) continue;
        await uploadEvidence(created.case_id, item.key, file, (value) => {
          setUploadProgress((prev) => ({ ...prev, [item.key]: value }));
        });
      }
      setStep("analysis");
      await analyzeCase(created.case_id);
      await runLogs();
      
      let isBackendComplete = false;
      for (let i = 0; i < 15; i++) {
        const data = await getAnalysisResults(created.case_id);
        if (data.status === "failed") {
          throw new Error(data.message || "Analysis failed on the backend");
        }
        if (data.status === "complete") {
          isBackendComplete = true;
          break;
        }
        await new Promise((r) => setTimeout(r, 2000));
      }

      if (!isBackendComplete) {
        throw new Error("Backend analysis did not complete in time. Check the case again in a moment.");
      }
      const report = await getReport(created.case_id);
      onComplete(report, { ...created, status: "completed", risk_level: report.risk_level, risk_score: report.risk_score });
      setStep("results");
    } catch (error) {
      console.error("Investigation flow failed", error);
      alert(error instanceof Error ? error.message : "Investigation flow failed. Check the backend and try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AnimatePresence>
      {open ? (
        <motion.div className="fixed inset-0 z-40 grid place-items-center bg-slate-950/70 p-4 backdrop-blur-xl" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <motion.div
            className="glass thin-scrollbar max-h-[92vh] w-full max-w-5xl overflow-y-auto rounded-[2rem] p-5 shadow-[0_0_90px_rgba(34,211,238,.18)] md:p-7"
            initial={{ opacity: 0, scale: 0.92, y: 24 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 16 }}
          >
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <Badge tone="violet">Investigation Workflow</Badge>
                <h2 className="mt-3 text-3xl font-black text-white">Create case and launch AI analysis</h2>
              </div>
              <Button variant="ghost" onClick={onClose}>Close</Button>
            </div>
            <StepHeader step={step} />

            <AnimatePresence mode="wait">
              {step === "case" ? (
                <motion.div key="case" initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -24 }} className="mt-6 grid gap-4 md:grid-cols-2">
                  <Field label="Case Title"><Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="Operation Midnight Route" /></Field>
                  <Field label="Victim Name"><Input value={form.victim_name} onChange={(e) => setForm({ ...form, victim_name: e.target.value })} placeholder="Victim name" /></Field>
                  <Field label="Incident Location"><Input value={form.incident_location} onChange={(e) => setForm({ ...form, incident_location: e.target.value })} placeholder="City, scene, landmark" /></Field>
                  <Field label="Incident Date"><Input type="date" value={form.incident_date} onChange={(e) => setForm({ ...form, incident_date: e.target.value })} /></Field>
                  <Field label="Priority Level">
                    <select className="h-11 w-full rounded-xl border border-white/10 bg-slate-950/50 px-3 text-sm text-white outline-none" value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}>
                      <option>HIGH</option>
                      <option>MEDIUM</option>
                      <option>LOW</option>
                    </select>
                  </Field>
                  <Field label="Investigation Notes" className="md:col-span-2"><Textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="Initial narrative, last-seen details, scene notes, witness hints..." /></Field>
                  <div className="md:col-span-2 flex justify-end gap-3">
                    <Button variant="secondary" onClick={onClose}>Cancel</Button>
                    <Button onClick={() => setStep("upload")}>Next Step <ChevronRight className="h-4 w-4" /></Button>
                  </div>
                </motion.div>
              ) : null}

              {step === "upload" ? (
                <motion.div key="upload" initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -24 }} className="mt-6">
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                    {evidenceTypes.map((type) => (
                      <label key={type.key} className="group relative cursor-pointer overflow-hidden rounded-3xl border border-dashed border-cyan-300/25 bg-cyan-300/[0.04] p-5 transition hover:border-cyan-200/60">
                        <input type="file" accept={type.accept} className="hidden" onChange={(e) => setFiles((prev) => ({ ...prev, [type.key]: e.target.files?.[0] || null }))} />
                        <div className="flex items-center gap-3">
                          <div className="grid h-11 w-11 place-items-center rounded-2xl bg-cyan-300/10"><type.icon className="h-5 w-5 text-cyan-200" /></div>
                          <div>
                            <p className="font-semibold text-white">{type.label}</p>
                            <p className="text-xs text-slate-400">{files[type.key]?.name || "Drop or choose file"}</p>
                          </div>
                        </div>
                        <div className="mt-5"><Progress value={uploadProgress[type.key] || (files[type.key] ? 28 : 0)} /></div>
                      </label>
                    ))}
                  </div>
                  <div className="mt-6 flex justify-end gap-3">
                    <Button variant="secondary" onClick={() => setStep("case")}>Back</Button>
                    <Button disabled={busy} onClick={createAndUpload}>{busy ? "Launching AI..." : "Upload & Analyze"} <Sparkles className="h-4 w-4" /></Button>
                  </div>
                </motion.div>
              ) : null}

              {step === "analysis" ? (
                <motion.div key="analysis" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="mt-6 grid gap-6 lg:grid-cols-[.8fr_1.2fr]">
                  <div className="scanline relative grid min-h-96 place-items-center overflow-hidden rounded-3xl border border-cyan-300/20 bg-slate-950/50">
                    <motion.div className="h-52 w-52 rounded-full border border-cyan-300/30" animate={{ rotate: 360 }} transition={{ duration: 8, repeat: Infinity, ease: "linear" }} />
                    <div className="absolute text-center">
                      <BrainCircuit className="mx-auto h-12 w-12 text-cyan-200" />
                      <p className="mt-4 text-4xl font-black">{progress}%</p>
                      <p className="text-sm text-slate-400">AI forensic scan</p>
                    </div>
                  </div>
                  <Card>
                    <CardHeader><CardTitle>Streaming AI Logs</CardTitle></CardHeader>
                    <CardContent className="space-y-3">
                      <Progress value={progress} tone="violet" />
                      {logs.map((log) => (
                        <motion.div key={log} initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} className="rounded-2xl border border-white/10 bg-white/[0.04] p-3 text-sm text-cyan-100">
                          <span className="mr-2 text-emerald-300">OK</span>{log}
                        </motion.div>
                      ))}
                    </CardContent>
                  </Card>
                </motion.div>
              ) : null}

              {step === "results" ? (
                <motion.div key="results" initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }} className="mt-6">
                  <Card className="border-emerald-300/20 bg-emerald-300/8">
                    <CardContent className="flex flex-wrap items-center justify-between gap-4 p-5">
                      <div>
                        <p className="text-2xl font-black text-white">Analysis complete</p>
                        <p className="mt-1 text-sm text-slate-300">The new case is now loaded into the command dashboard.</p>
                      </div>
                      <Button onClick={onClose}>View Dashboard</Button>
                    </CardContent>
                  </Card>
                </motion.div>
              ) : null}
            </AnimatePresence>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

function StepHeader({ step }: { step: FlowStep }) {
  const steps: Array<{ key: FlowStep; label: string }> = [
    { key: "case", label: "Case" },
    { key: "upload", label: "Evidence" },
    { key: "analysis", label: "AI Analysis" },
    { key: "results", label: "Results" }
  ];
  const activeIndex = steps.findIndex((item) => item.key === step);
  return (
    <div className="mt-6 grid gap-3 sm:grid-cols-4">
      {steps.map((item, index) => (
        <div key={item.key} className={cn("rounded-2xl border p-3 text-sm font-semibold", index <= activeIndex ? "border-cyan-300/35 bg-cyan-300/10 text-cyan-100" : "border-white/10 bg-white/[0.03] text-slate-400")}>
          {index + 1}. {item.label}
        </div>
      ))}
    </div>
  );
}

function Field({ label, children, className }: { label: string; children: React.ReactNode; className?: string }) {
  return (
    <label className={className}>
      <span className="mb-2 block text-sm font-semibold text-slate-200">{label}</span>
      {children}
    </label>
  );
}
