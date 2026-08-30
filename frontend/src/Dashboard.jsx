import React, { useState, useEffect } from 'react';
import { TrendingDown, TrendingUp, AlertCircle, Zap, Activity } from 'lucide-react';

export default function Dashboard({ persona, selectedMovement, onSelect }) {
  const [movements, setMovements] = useState([]);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState(null);

  useEffect(() => {
    const fetchMovements = async () => {
      try {
        setLoading(true);
        const response = await fetch('/api/movements', {
          headers: { 'x-user-id': persona },
        });
        if (!response.ok) throw new Error('Failed to fetch movements');
        const data = await response.json();
        setMovements(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchMovements();
  }, [persona]);

  const fmt = (val) => {
    if (Math.abs(val) < 100) return val.toFixed(1);
    return (val / 1000).toFixed(1) + 'k';
  };

  /* ── Loading skeleton ── */
  if (loading) {
    return (
      <div className="space-y-2 mt-1">
        {[...Array(5)].map((_, i) => (
          <div
            key={i}
            className="h-[90px] rounded-xl animate-pulse mx-1"
            style={{
              background: 'rgba(86,102,119,0.12)',
              animationDelay: `${i * 0.09}s`,
            }}
          />
        ))}
      </div>
    );
  }

  /* ── Error state ── */
  if (error) {
    return (
      <div className="p-5 mt-2 text-center animate-fade-in">
        <AlertCircle className="w-6 h-6 text-red-400/60 mx-auto mb-2" />
        <p className="text-red-400/70 text-xs font-medium">Backend offline</p>
        <p className="text-w-mid/40 text-[11px] mt-1 font-mono">{error}</p>
      </div>
    );
  }

  /* ── Empty state ── */
  if (!movements.length) {
    return (
      <div className="p-5 mt-2 text-center animate-fade-in">
        <Activity className="w-6 h-6 text-w-mid/40 mx-auto mb-2" />
        <p className="text-w-mid/60 text-xs">No anomalies detected</p>
      </div>
    );
  }

  return (
    <div className="space-y-1.5 mt-1">
      {movements.map((movement, idx) => {
        const isNeg = movement.pct_change < 0;
        const isSelected =
          selectedMovement?.kpi_name   === movement.kpi_name &&
          selectedMovement?.region     === movement.region   &&
          selectedMovement?.period_end === movement.period_end;
        const Icon     = isNeg ? TrendingDown : TrendingUp;
        const dotColor = isNeg ? '#f87171' : '#4ade80';

        return (
          <button
            key={idx}
            onClick={() => onSelect(movement)}
            className="sidebar-item w-full text-left rounded-xl border transition-all duration-300 group relative overflow-hidden"
            style={{
              animationDelay: `${idx * 0.06}s`,
              background: isSelected
                ? 'rgba(176,191,209,0.07)'
                : 'rgba(86,102,119,0.07)',
              borderColor: isSelected
                ? 'rgba(176,191,209,0.22)'
                : 'rgba(86,102,119,0.22)',
              boxShadow: isSelected
                ? '0 0 24px rgba(176,191,209,0.10), 0 0 1px rgba(176,191,209,0.30)'
                : 'none',
            }}
            onMouseEnter={e => {
              if (!isSelected) {
                e.currentTarget.style.background   = 'rgba(86,102,119,0.14)';
                e.currentTarget.style.borderColor  = 'rgba(86,102,119,0.35)';
                e.currentTarget.style.boxShadow    = '0 4px 16px rgba(0,0,0,0.15)';
              }
            }}
            onMouseLeave={e => {
              if (!isSelected) {
                e.currentTarget.style.background   = 'rgba(86,102,119,0.07)';
                e.currentTarget.style.borderColor  = 'rgba(86,102,119,0.22)';
                e.currentTarget.style.boxShadow    = 'none';
              }
            }}
          >
            {/* Active left accent bar */}
            <div
              className="absolute left-0 top-3 bottom-3 w-[3px] rounded-full transition-all duration-300"
              style={{
                background: '#B0BFD1',
                opacity: isSelected ? 1 : 0,
                boxShadow: isSelected ? '0 0 8px rgba(176,191,209,0.6)' : 'none',
              }}
            />

            <div className="px-4 py-3.5 pl-5">
              {/* Row 1: KPI name + trend badge */}
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center space-x-2 min-w-0">
                  <div
                    className="flex-shrink-0 w-2 h-2 rounded-full transition-all duration-300"
                    style={{
                      backgroundColor: dotColor,
                      boxShadow: `0 0 ${isSelected ? '12px' : '6px'} ${dotColor}`,
                    }}
                  />
                  <span
                    className="text-sm font-semibold truncate transition-colors duration-200"
                    style={{ color: isSelected ? '#B0BFD1' : 'rgba(176,191,209,0.80)' }}
                  >
                    {movement.kpi_name}
                  </span>
                </div>

                <span
                  className={`flex-shrink-0 ml-2 text-xs font-bold flex items-center gap-0.5 px-1.5 py-0.5 rounded-md border ${
                    isNeg
                      ? 'text-red-400 bg-red-500/8 border-red-500/18'
                      : 'text-green-400 bg-green-500/8 border-green-500/18'
                  }`}
                >
                  <Icon className="w-3 h-3" strokeWidth={2.5} />
                  {movement.pct_change?.toFixed(1)}%
                </span>
              </div>

              {/* Row 2: Region + z-score + impact */}
              <div className="flex items-center justify-between text-xs">
                <span className="text-w-mid/60 font-medium">{movement.region}</span>
                <div className="flex items-center space-x-2 font-mono text-w-mid/60">
                  <span>z={movement.z_score.toFixed(1)}</span>
                  <span
                    className="font-semibold transition-colors duration-200"
                    style={{ color: isSelected ? '#B0BFD1' : 'rgba(176,191,209,0.50)' }}
                  >
                    ${fmt(movement.dollar_impact)}
                  </span>
                </div>
              </div>

              {/* Row 3: Drill In hint — shown on hover / active */}
              <div
                className="mt-2.5 pt-2 flex items-center justify-between text-xs transition-all duration-200"
                style={{
                  borderTop: '1px solid rgba(86,102,119,0.22)',
                  opacity: isSelected ? 1 : 0,
                }}
              >
                <span className="flex items-center gap-1 font-semibold" style={{ color: '#B0BFD1' }}>
                  <Zap className="w-3 h-3" />
                  Drill In →
                </span>
                <span className="text-w-mid/40 font-mono">{movement.period_end}</span>
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}
