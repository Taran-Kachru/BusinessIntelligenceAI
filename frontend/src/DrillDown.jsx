import React, { useState, useEffect } from 'react';
import {
  X, TrendingDown, TrendingUp, AlertTriangle, Clock, Fingerprint,
  Shield, Cpu, BookOpen, Lightbulb, ChevronDown, ChevronRight, BarChart2,
  ArrowLeft,
} from 'lucide-react';
import {
  Area, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceArea, ComposedChart,
} from 'recharts';

/* ── Wealth colour tokens ───────────────────────────────── */
const C = {
  dark:   '#103438',
  darker: '#0c2c30',
  mid:    '#566677',
  silver: '#B0BFD1',
};

/* ── Chart tooltip ── */
const ChartTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: '#0c2c30', border: '1px solid rgba(86,102,119,0.4)', borderRadius: 10, padding: '10px 14px' }} className="text-xs shadow-2xl">
      <p style={{ color: C.mid }} className="mb-1 font-mono">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }} className="font-mono">
          {p.name}:{' '}
          {typeof p.value === 'number'
            ? Math.abs(p.value) >= 1000 ? `${(p.value / 1000).toFixed(1)}k` : p.value.toFixed(3)
            : p.value}
        </p>
      ))}
    </div>
  );
};

const yFmt = (v) => Math.abs(v) >= 1000 ? `${(v / 1000).toFixed(0)}k` : parseFloat(v.toFixed(2));

/* ── Reusable section heading ── */
const SectionHeading = ({ icon: Icon, children, sub }) => (
  <div className="flex items-center justify-between">
    <h3 className="text-[11px] font-bold uppercase tracking-widest flex items-center gap-2" style={{ color: C.mid }}>
      <Icon className="w-4 h-4" />
      {children}
    </h3>
    {sub && (
      <span
        className="text-[10px] font-mono px-2 py-0.5 rounded-md"
        style={{
          background: 'rgba(86,102,119,0.15)',
          color: 'rgba(176,191,209,0.55)',
          border: '1px solid rgba(86,102,119,0.25)',
        }}
      >
        {sub}
      </span>
    )}
  </div>
);

export default function DrillDown({ movement, persona, onClose }) {
  const [insight,          setInsight]          = useState(null);
  const [narrative,        setNarrative]        = useState(null);
  const [actions,          setActions]          = useState([]);
  const [history,          setHistory]          = useState(null);
  const [loading,          setLoading]          = useState(true);
  const [error,            setError]            = useState(null);
  const [expandedEvidence, setExpandedEvidence] = useState(null);

  useEffect(() => {
    if (!movement) return;
    let alive = true;
    const load = async () => {
      try {
        setLoading(true);
        const headers = { 'x-user-id': persona };
        const p = new URLSearchParams({
          kpi_name:     movement.kpi_name,
          region:       movement.region,
          period_start: movement.period_start,
          period_end:   movement.period_end,
        });
        const hp = new URLSearchParams({ kpi_name: movement.kpi_name, region: movement.region, days: 60 });

        const [resInsight, resHistory] = await Promise.all([
          fetch(`/api/insight?${p}`, { headers }),
          fetch(`/api/kpi/history?${hp}`, { headers }),
        ]);
        if (!resInsight.ok) throw new Error('Failed to load insight');

        const insightData = await resInsight.json();
        const historyData = resHistory.ok ? await resHistory.json() : null;

        const [resNarrative, resActions] = await Promise.all([
          fetch(`/api/insight/narrative?${p}`, { method: 'POST', headers }),
          fetch(`/api/insight/actions?${p}`,   { method: 'POST', headers }),
        ]);

        if (alive) {
          setInsight(insightData);
          setHistory(historyData);
          if (resNarrative.ok) setNarrative(await resNarrative.json());
          if (resActions.ok)   setActions(await resActions.json());
        }
      } catch (err) {
        if (alive) setError(err.message);
      } finally {
        if (alive) setLoading(false);
      }
    };
    load();
    return () => { alive = false; };
  }, [movement, persona]);

  if (!movement) return null;

  const firstCurrentDate = history?.series?.find((d) => d.in_current_period)?.date;
  const lastCurrentDate  = [...(history?.series ?? [])].reverse().find((d) => d.in_current_period)?.date;

  return (
    <div className="h-full flex flex-col overflow-hidden animate-slide-in-right">

      {/* ── Panel header ── */}
      <div
        className="flex justify-between items-center px-8 py-5 shrink-0"
        style={{
          background: 'rgba(10,28,32,0.80)',
          borderBottom: '1px solid rgba(86,102,119,0.25)',
          backdropFilter: 'blur(12px)',
        }}
      >
        <div className="flex items-center space-x-4">
          {/* Back */}
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg transition-all duration-200 group"
            style={{ background: 'rgba(86,102,119,0.10)', border: '1px solid rgba(86,102,119,0.20)' }}
            title="Back"
          >
            <ArrowLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform duration-150" style={{ color: C.silver }} />
          </button>

          <div>
            {/* Breadcrumb */}
            <div className="flex items-center space-x-1.5 text-[11px] font-mono mb-1 uppercase tracking-wider" style={{ color: C.mid }}>
              <span>{movement.period_start}</span>
              <span style={{ opacity: 0.4 }}>→</span>
              <span>{movement.period_end}</span>
              <span style={{ color: 'rgba(86,102,119,0.35)' }}>·</span>
              <span style={{ color: 'rgba(176,191,209,0.60)' }}>{movement.region} Region</span>
            </div>

            {/* KPI name + trend badge */}
            <h2 className="text-2xl font-bold tracking-tight flex items-center gap-3" style={{ color: '#fff' }}>
              {movement.kpi_name}
              <span
                className="text-sm font-bold px-2.5 py-0.5 rounded-lg flex items-center gap-1.5"
                style={movement.pct_change < 0
                  ? { background: 'rgba(248,113,113,0.12)', color: '#f87171', border: '1px solid rgba(248,113,113,0.22)' }
                  : { background: 'rgba(74,222,128,0.10)', color: '#4ade80', border: '1px solid rgba(74,222,128,0.20)' }}
              >
                {movement.pct_change < 0
                  ? <TrendingDown className="w-4 h-4" />
                  : <TrendingUp   className="w-4 h-4" />}
                {movement.pct_change?.toFixed(1)}%
              </span>
            </h2>
          </div>
        </div>

        <button
          onClick={onClose}
          className="p-2 rounded-full transition-colors"
          style={{ color: C.mid }}
          onMouseEnter={e => e.currentTarget.style.color = C.silver}
          onMouseLeave={e => e.currentTarget.style.color = C.mid}
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* ── Scrollable body ── */}
      <div className="flex-1 overflow-y-auto p-8 space-y-8 scrollbar-thin">

        {/* Loading */}
        {loading ? (
          <div className="flex flex-col items-center justify-center py-28 space-y-4 animate-fade-in">
            <div
              className="w-10 h-10 border-4 border-t-transparent rounded-full animate-spin"
              style={{ borderColor: 'rgba(176,191,209,0.35)', borderTopColor: 'transparent' }}
            />
            <p className="text-[11px] tracking-widest uppercase font-mono" style={{ color: 'rgba(176,191,209,0.50)' }}>
              Assembling Intelligence…
            </p>
          </div>

        ) : error ? (
          <div
            className="p-6 rounded-xl animate-fade-in"
            style={{ background: 'rgba(248,113,113,0.07)', border: '1px solid rgba(248,113,113,0.22)' }}
          >
            <p className="text-red-400 text-sm">Error: {error}</p>
          </div>

        ) : (
          <>
            {/* Abstention banner */}
            {insight?.confidence?.should_abstain && (
              <div
                className="p-5 rounded-xl flex items-start space-x-4 animate-fade-in"
                style={{ background: 'rgba(251,146,60,0.08)', border: '1px solid rgba(251,146,60,0.30)' }}
              >
                <AlertTriangle className="w-6 h-6 text-orange-400 mt-1 shrink-0" />
                <div>
                  <h4 className="text-lg font-bold text-orange-400 mb-1">Insufficient Confidence to Conclude</h4>
                  <p className="text-sm leading-relaxed mb-3" style={{ color: 'rgba(176,191,209,0.80)' }}>
                    {insight.confidence.abstention_reason}
                  </p>
                  {insight.confidence.clarifying_question && (
                    <div className="p-3 rounded border" style={{ background: 'rgba(251,146,60,0.07)', border: '1px solid rgba(251,146,60,0.20)' }}>
                      <span className="block text-orange-300 font-bold font-mono text-[10px] mb-1 uppercase tracking-wider">Recommended Question:</span>
                      <span style={{ color: C.silver }}>{insight.confidence.clarifying_question}</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* 60-Day trend chart */}
            {history?.series?.length > 0 && (
              <div
                className="p-5 rounded-xl animate-fade-in"
                style={{ background: 'rgba(10,28,32,0.55)', border: '1px solid rgba(86,102,119,0.22)' }}
              >
                <SectionHeading icon={BarChart2} sub="Computed by: DuckDB SQL · 28d rolling mean">
                  60-Day Trend
                </SectionHeading>

                <div className="h-52 mt-4">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={history.series} margin={{ top: 4, right: 8, left: 4, bottom: 4 }}>
                      <defs>
                        <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%"  stopColor={C.silver} stopOpacity={0.22} />
                          <stop offset="95%" stopColor={C.silver} stopOpacity={0.0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(86,102,119,0.20)" />
                      <XAxis
                        dataKey="date"
                        tick={{ fill: C.mid, fontSize: 10 }}
                        tickLine={false}
                        interval={Math.max(1, Math.floor(history.series.length / 8))}
                      />
                      <YAxis
                        tick={{ fill: C.mid, fontSize: 10 }}
                        tickLine={false}
                        axisLine={false}
                        tickFormatter={yFmt}
                        width={46}
                      />
                      <Tooltip content={<ChartTooltip />} />
                      {firstCurrentDate && lastCurrentDate && (
                        <ReferenceArea
                          x1={firstCurrentDate}
                          x2={lastCurrentDate}
                          fill={C.silver}
                          fillOpacity={0.06}
                          stroke={C.silver}
                          strokeOpacity={0.30}
                          strokeDasharray="4 2"
                          label={{ value: 'Current Period', position: 'insideTopRight', fill: 'rgba(176,191,209,0.60)', fontSize: 9 }}
                        />
                      )}
                      <Area
                        type="monotone"
                        dataKey="value"
                        stroke={C.silver}
                        strokeWidth={2}
                        fill="url(#areaGrad)"
                        name="Actual"
                        dot={false}
                        activeDot={{ r: 3, fill: C.silver, stroke: C.dark }}
                      />
                      <Line
                        type="monotone"
                        dataKey="rolling_mean"
                        stroke={C.mid}
                        strokeWidth={1.5}
                        strokeDasharray="5 3"
                        dot={false}
                        name="28d Mean"
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {/* Persona narrative */}
            {narrative && (
              <div
                className="p-6 rounded-xl relative overflow-hidden animate-fade-in"
                style={{ background: 'rgba(86,102,119,0.06)', border: '1px solid rgba(176,191,209,0.12)' }}
              >
                {/* Left gradient bar */}
                <div
                  className="absolute top-0 left-0 w-[3px] h-full"
                  style={{ background: 'linear-gradient(to bottom, rgba(176,191,209,0.60), rgba(176,191,209,0.05))' }}
                />
                <div className="flex items-center space-x-2 text-[11px] font-bold mb-3 tracking-widest uppercase" style={{ color: C.silver }}>
                  <Cpu className="w-4 h-4" />
                  <span>Generated for {narrative.persona}</span>
                </div>
                <p className="text-lg leading-relaxed font-light" style={{ color: 'rgba(176,191,209,0.90)' }}>
                  {narrative.text}
                </p>
                <div
                  className="mt-4 pt-4 flex justify-between items-center text-xs font-mono"
                  style={{ borderTop: '1px solid rgba(86,102,119,0.18)' }}
                >
                  <span className="flex items-center" style={{ color: C.mid }}>
                    <Shield className="w-3 h-3 mr-1" /> Deterministically Grounded
                  </span>
                  {narrative.is_fallback ? (
                    <span className="px-2 py-0.5 rounded font-bold bg-amber-900/25 text-amber-400 border border-amber-700/30">
                      ⚠ Template Fallback — set GEMINI_API_KEY in .env
                    </span>
                  ) : (
                    <span className="px-2 py-0.5 rounded font-bold bg-emerald-900/20 text-emerald-400 border border-emerald-700/25">
                      ✓ {narrative.model_used}
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* Drivers + Actions */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 animate-fade-in">

              {/* Quantified root causes */}
              <div className="space-y-3">
                <SectionHeading icon={BookOpen}>Quantified Root Causes</SectionHeading>
                <div className="space-y-2">
                  {insight?.drivers?.drivers?.map((driver, idx) => (
                    <div
                      key={idx}
                      className="p-4 rounded-xl transition-all duration-200"
                      style={{
                        background: 'rgba(86,102,119,0.08)',
                        border: '1px solid rgba(86,102,119,0.22)',
                      }}
                      onMouseEnter={e => e.currentTarget.style.background = 'rgba(86,102,119,0.14)'}
                      onMouseLeave={e => e.currentTarget.style.background = 'rgba(86,102,119,0.08)'}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="font-semibold text-sm" style={{ color: C.silver }}>{driver.driver_name}</p>
                          <p className="text-[11px] mt-0.5 font-mono" style={{ color: C.mid }}>Method: {driver.method}</p>
                        </div>
                        <div
                          className="font-mono font-bold text-sm"
                          style={{ color: driver.direction === '-' ? '#f87171' : '#4ade80' }}
                        >
                          {driver.effect_pct > 0 ? `${driver.effect_pct.toFixed(1)}%` : 'Unquantified'}
                        </div>
                      </div>
                    </div>
                  ))}
                  {!insight?.drivers?.drivers?.length && (
                    <p className="text-sm italic" style={{ color: C.mid }}>No quantifiable drivers found.</p>
                  )}
                </div>
              </div>

              {/* Recommended actions */}
              <div className="space-y-3">
                <SectionHeading icon={Lightbulb}>Recommended Actions</SectionHeading>
                <div className="space-y-2.5">
                  {actions?.map((act, idx) => (
                    <div
                      key={idx}
                      className="p-4 rounded-xl"
                      style={act.exceeds_authority
                        ? { background: 'rgba(251,146,60,0.07)', border: '1px solid rgba(251,146,60,0.22)' }
                        : { background: 'rgba(86,102,119,0.08)', border: '1px solid rgba(86,102,119,0.22)' }}
                    >
                      <div className="flex justify-between items-start mb-2">
                        <span
                          className="text-[10px] font-bold uppercase px-2 py-0.5 rounded"
                          style={{ background: 'rgba(86,102,119,0.25)', color: 'rgba(176,191,209,0.70)' }}
                        >
                          {act.confidence} Confidence
                        </span>
                        {act.exceeds_authority && (
                          <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-orange-500/18 text-orange-400 flex items-center">
                            <Shield className="w-3 h-3 mr-1" />
                            Escalated to {act.owner}
                          </span>
                        )}
                      </div>
                      <p className="text-sm font-medium mb-1" style={{ color: C.silver }}>{act.action}</p>
                      <p className="text-xs" style={{ color: C.mid }}>
                        <span style={{ color: 'rgba(86,102,119,0.60)' }}>Impact:</span> {act.expected_impact}
                      </p>
                      {act.monitoring_plan && (
                        <p className="text-xs mt-0.5" style={{ color: 'rgba(86,102,119,0.60)' }}>
                          <span style={{ color: 'rgba(86,102,119,0.45)' }}>Monitor:</span> {act.monitoring_plan}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Evidence & Provenance */}
            {insight?.evidence?.length > 0 && (
              <div className="space-y-3 animate-fade-in">
                <div className="flex items-center gap-2">
                  <SectionHeading icon={Fingerprint}>Evidence &amp; Provenance</SectionHeading>
                  <span className="text-[11px] font-normal" style={{ color: 'rgba(86,102,119,0.50)' }}>
                    — click any row for raw details
                  </span>
                </div>
                <div className="space-y-1.5">
                  {insight.evidence.map((ev, idx) => (
                    <div
                      key={idx}
                      className="rounded-xl overflow-hidden"
                      style={{ background: 'rgba(10,28,32,0.55)', border: '1px solid rgba(86,102,119,0.20)' }}
                    >
                      <button
                        className="w-full flex items-center justify-between p-3 text-left gap-3 transition-colors"
                        style={{ borderRadius: 'inherit' }}
                        onClick={() => setExpandedEvidence(expandedEvidence === idx ? null : idx)}
                        onMouseEnter={e => e.currentTarget.style.background = 'rgba(86,102,119,0.12)'}
                        onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <span className="text-xs font-mono font-bold shrink-0" style={{ color: C.silver }}>
                            {ev.evidence_id}
                          </span>
                          <span className="text-sm truncate" style={{ color: 'rgba(176,191,209,0.75)' }}>
                            {ev.metric.replace(/_/g, ' ')}
                          </span>
                          <span
                            className="text-[10px] font-mono px-1.5 py-0.5 rounded shrink-0 whitespace-nowrap"
                            style={{ background: 'rgba(86,102,119,0.18)', color: 'rgba(176,191,209,0.55)', border: '1px solid rgba(86,102,119,0.28)' }}
                          >
                            Computed by: {ev.method}
                          </span>
                        </div>
                        <div className="flex items-center gap-3 shrink-0">
                          <span className="text-sm font-mono font-bold" style={{ color: C.silver }}>
                            {Math.abs(ev.value) >= 1000
                              ? `${(ev.value / 1000).toFixed(1)}k`
                              : typeof ev.value === 'number' ? ev.value.toFixed(3) : ev.value}
                          </span>
                          {expandedEvidence === idx
                            ? <ChevronDown  className="w-4 h-4" style={{ color: C.mid }} />
                            : <ChevronRight className="w-4 h-4" style={{ color: C.mid }} />}
                        </div>
                      </button>

                      {expandedEvidence === idx && (
                        <div
                          className="px-4 pb-4 pt-3 animate-fade-in"
                          style={{ borderTop: '1px solid rgba(86,102,119,0.18)', background: 'rgba(8,24,28,0.70)' }}
                        >
                          <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-xs font-mono">
                            <span style={{ color: C.mid }}>Source Table</span>
                            <span style={{ color: 'rgba(176,191,209,0.80)' }}>{ev.source_table}</span>

                            <span style={{ color: C.mid }}>Metric</span>
                            <span style={{ color: 'rgba(176,191,209,0.80)' }}>{ev.metric}</span>

                            <span style={{ color: C.mid }}>Current Value</span>
                            <span className="font-bold" style={{ color: C.silver }}>{ev.value}</span>

                            {ev.comparison_value != null && (
                              <>
                                <span style={{ color: C.mid }}>Comparison Value</span>
                                <span style={{ color: 'rgba(176,191,209,0.80)' }}>{ev.comparison_value}</span>
                              </>
                            )}

                            <span style={{ color: C.mid }}>Analytical Method</span>
                            <span className="text-emerald-400">{ev.method}</span>

                            {ev.freshness && (
                              <>
                                <span style={{ color: C.mid }}>Data Freshness</span>
                                <span className={
                                  ev.freshness.freshness_status === 'STALE' ? 'text-red-400' :
                                  ev.freshness.freshness_status === 'AGING' ? 'text-amber-400' : 'text-emerald-400'
                                }>
                                  {ev.freshness.freshness_status} · {ev.freshness.native_grain} grain
                                  {ev.freshness.last_refresh ? ` · last: ${ev.freshness.last_refresh}` : ''}
                                </span>
                              </>
                            )}

                            {ev.note && (
                              <>
                                <span style={{ color: C.mid }}>Analyst Note</span>
                                <span style={{ color: 'rgba(176,191,209,0.75)' }}>{ev.note}</span>
                              </>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Freshness footer */}
            <div
              className="p-4 rounded-xl flex flex-wrap items-center gap-4 text-xs font-mono animate-fade-in"
              style={{ background: 'rgba(8,24,28,0.70)', border: '1px solid rgba(86,102,119,0.18)' }}
            >
              <div className="flex items-center gap-2" style={{ color: C.mid }}>
                <Fingerprint className="w-4 h-4 text-emerald-500/60" />
                <span>Verified Lineage</span>
              </div>
              {insight?.freshness?.map((f, i) => (
                <div key={i} className="flex items-center gap-1.5" style={{ color: C.mid }}>
                  <Clock className={`w-3 h-3 ${
                    f.freshness_status === 'STALE' ? 'text-red-400' :
                    f.freshness_status === 'AGING' ? 'text-amber-400' : 'text-emerald-500'
                  }`} />
                  <span>
                    {f.table_name}:{' '}
                    <span className={
                      f.freshness_status === 'STALE' ? 'text-red-400' :
                      f.freshness_status === 'AGING' ? 'text-amber-400' : 'text-emerald-400'
                    }>
                      {f.freshness_status}
                    </span>
                  </span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
