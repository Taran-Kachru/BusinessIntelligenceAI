import React, { useState } from 'react';
import { BarChart2, Sparkles, ChevronDown, TrendingUp } from 'lucide-react';
import Dashboard from './Dashboard';
import DrillDown from './DrillDown';

function WelcomeScreen() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center px-12 animate-fade-in select-none">

      {/* Central icon */}
      <div
        className="p-7 rounded-3xl border border-w-mid/20 mb-8"
        style={{
          background: 'rgba(86,102,119,0.08)',
          boxShadow: '0 0 60px rgba(176,191,209,0.06), 0 0 1px rgba(176,191,209,0.12)',
        }}
      >
        <BarChart2 className="w-14 h-14 text-w-silver/50" />
      </div>

      {/* Headline */}
      <h2 className="text-2xl font-bold text-w-silver mb-3 tracking-tight">
        Select a KPI to Explore
      </h2>
      <p className="text-w-mid max-w-xs text-sm leading-relaxed">
        Pick an anomaly from the sidebar to see AI-generated insights, root-cause drivers, and recommended actions.
      </p>

      {/* Premium divider */}
      <div className="mt-10 flex items-center space-x-4">
        <span className="w-12 h-px bg-w-mid/20" />
        <span className="text-w-mid/40 text-[10px] font-mono uppercase tracking-widest">
          Numbers are deterministic · LLM writes only the words
        </span>
        <span className="w-12 h-px bg-w-mid/20" />
      </div>

      {/* Subtle feature chips */}
      <div className="mt-8 flex flex-wrap justify-center gap-2">
        {['Statistical Significance', 'Driver Attribution', 'Persona Narratives', 'Governed Evidence'].map(f => (
          <span
            key={f}
            className="text-[10px] font-medium px-2.5 py-1 rounded-full border border-w-mid/20 text-w-mid/60"
            style={{ background: 'rgba(86,102,119,0.07)' }}
          >
            {f}
          </span>
        ))}
      </div>
    </div>
  );
}

export default function App() {
  const [persona, setPersona] = useState('CEO');
  const [selectedMovement, setSelectedMovement] = useState(null);

  const handlePersonaChange = (e) => {
    setPersona(e.target.value);
    setSelectedMovement(null);
  };

  return (
    <div className="flex h-screen overflow-hidden bg-w-dark">

      {/* ═══════════ SIDEBAR ═══════════ */}
      <aside
        className="w-[290px] flex-shrink-0 flex flex-col border-r border-w-mid/20"
        style={{ background: 'rgba(10,28,32,0.82)', backdropFilter: 'blur(24px)' }}
      >
        {/* Logo — with top shimmer line */}
        <div className="relative px-5 py-5 border-b border-w-mid/20">
          {/* Shimmer accent at top */}
          <div
            className="absolute top-0 left-5 right-5 h-px"
            style={{ background: 'linear-gradient(90deg, transparent, rgba(176,191,209,0.25), transparent)' }}
          />
          <div className="flex items-center space-x-3">
            <div
              className="p-1.5 rounded-lg border border-w-mid/35"
              style={{
                background: 'rgba(176,191,209,0.08)',
                boxShadow: '0 0 16px rgba(176,191,209,0.12)',
              }}
            >
              <BarChart2 className="w-5 h-5 text-w-silver" />
            </div>
            <h1
              className="text-lg font-bold tracking-tight bg-clip-text text-transparent"
              style={{ backgroundImage: 'linear-gradient(135deg, #fff 0%, #B0BFD1 60%, #566677 100%)' }}
            >
              KPI Pulse.ai
            </h1>
          </div>
        </div>

        {/* Persona selector */}
        <div className="px-4 py-3.5 border-b border-w-mid/20">
          <div className="flex items-center space-x-1.5 mb-2">
            <Sparkles className="w-3 h-3 text-w-mid" />
            <span className="text-[10px] font-bold uppercase tracking-widest text-w-mid/60">View as persona</span>
          </div>
          <div className="relative">
            <select
              value={persona}
              onChange={handlePersonaChange}
              className="w-full appearance-none text-w-silver text-sm font-medium px-3 py-2 pr-8 rounded-lg focus:outline-none transition-all cursor-pointer"
              style={{
                background: 'rgba(86,102,119,0.14)',
                border: '1px solid rgba(86,102,119,0.32)',
              }}
            >
              <option value="CEO" style={{ background: '#103438' }}>CEO</option>
              <option value="Regional_Manager_West" style={{ background: '#103438' }}>Regional Manager (West)</option>
              <option value="Regional_Manager_East" style={{ background: '#103438' }}>Regional Manager (East)</option>
            </select>
            <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-w-mid/60 pointer-events-none" />
          </div>
        </div>

        {/* Section label */}
        <div className="px-4 pt-4 pb-2 flex items-center justify-between">
          <span className="text-[10px] font-bold uppercase tracking-widest text-w-mid/60">Anomaly Radar</span>
          <span className="text-[10px] text-w-mid/40 font-mono tracking-wide flex items-center gap-1">
            <TrendingUp className="w-3 h-3" />
            AI Prioritized
          </span>
        </div>

        {/* KPI list */}
        <div className="flex-1 overflow-y-auto px-2 pb-4 scrollbar-thin">
          <Dashboard
            persona={persona}
            selectedMovement={selectedMovement}
            onSelect={setSelectedMovement}
          />
        </div>

        {/* Sidebar footer */}
        <div className="px-4 py-3 border-t border-w-mid/15">
          <p className="text-[10px] text-w-mid/35 font-mono text-center">
            KPI Pulse · Accenture Innovation 2026
          </p>
        </div>
      </aside>

      {/* ═══════════ MAIN CONTENT ═══════════ */}
      <main className="flex-1 overflow-hidden relative">
        {/* Ambient depth glows */}
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div
            className="absolute top-[-100px] left-1/3 w-[700px] h-[700px] rounded-full blur-[140px]"
            style={{ background: 'rgba(176,191,209,0.03)' }}
          />
          <div
            className="absolute bottom-[-100px] right-1/4 w-[500px] h-[500px] rounded-full blur-[120px]"
            style={{ background: 'rgba(86,102,119,0.07)' }}
          />
        </div>

        <div className="relative h-full">
          {selectedMovement ? (
            <DrillDown
              key={`${selectedMovement.kpi_name}|${selectedMovement.region}|${selectedMovement.period_end}`}
              movement={selectedMovement}
              persona={persona}
              onClose={() => setSelectedMovement(null)}
            />
          ) : (
            <WelcomeScreen />
          )}
        </div>
      </main>
    </div>
  );
}
