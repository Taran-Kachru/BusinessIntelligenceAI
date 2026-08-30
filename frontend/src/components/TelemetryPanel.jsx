import React, { useState, useEffect } from 'react';
import { Activity, Clock, Zap, Database, DollarSign, Cpu } from 'lucide-react';

const PAID_FLASH_INPUT_PER_1M = 0.075;
const PAID_FLASH_OUTPUT_PER_1M = 0.30;
const SCALE_INSIGHTS_PER_MONTH = 10000;

function projectedCostAtScale(totalPromptTokens, totalCompletionTokens, totalCalls) {
  if (totalCalls === 0) return 0;
  const avgPrompt = totalPromptTokens / totalCalls;
  const avgCompletion = totalCompletionTokens / totalCalls;
  return (
    (avgPrompt / 1_000_000) * PAID_FLASH_INPUT_PER_1M * SCALE_INSIGHTS_PER_MONTH +
    (avgCompletion / 1_000_000) * PAID_FLASH_OUTPUT_PER_1M * SCALE_INSIGHTS_PER_MONTH
  );
}

export default function TelemetryPanel() {
  const [data, setData] = useState(null);

  useEffect(() => {
    const fetch_ = () => {
      fetch('/api/telemetry/session')
        .then(r => r.json())
        .then(setData)
        .catch(() => {});
    };
    fetch_();
    const id = setInterval(fetch_, 5000);
    return () => clearInterval(id);
  }, []);

  if (!data) {
    return (
      <div className="p-6 bg-slate-800/40 border border-slate-700/50 rounded-xl animate-pulse">
        <div className="h-4 bg-slate-700 rounded w-1/3 mb-4" />
        <div className="grid grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => <div key={i} className="h-16 bg-slate-700 rounded" />)}
        </div>
      </div>
    );
  }

  const totalTokens = (data.total_prompt_tokens || 0) + (data.total_completion_tokens || 0);
  const avgLatency = data.total_calls > 0 ? ((data.total_latency_ms || 0) / data.total_calls).toFixed(0) : 0;
  const cacheHitPct = ((data.cache_hit_rate || 0) * 100).toFixed(0);
  const projCost = projectedCostAtScale(data.total_prompt_tokens, data.total_completion_tokens, data.total_calls);

  const statCards = [
    { icon: Zap, label: 'Total Tokens', value: totalTokens.toLocaleString(), sub: `${data.total_prompt_tokens} in / ${data.total_completion_tokens} out`, color: 'text-yellow-400' },
    { icon: DollarSign, label: 'Cost (Free Tier)', value: '$0.00', sub: `~$${projCost.toFixed(2)}/mo at ${SCALE_INSIGHTS_PER_MONTH.toLocaleString()} insights (paid Flash)`, color: 'text-green-400' },
    { icon: Clock, label: 'Avg Latency', value: `${avgLatency} ms`, sub: `${data.total_calls} total calls`, color: 'text-blue-400' },
    { icon: Database, label: 'Cache Hit Rate', value: `${cacheHitPct}%`, sub: `${Math.round((data.cache_hit_rate || 0) * data.total_calls)} hits saved`, color: 'text-purple-400' },
  ];

  return (
    <div className="p-6 bg-slate-800/40 border border-slate-700/50 rounded-xl space-y-6">
      <div className="flex items-center space-x-2">
        <Activity className="text-purple-400" size={20} />
        <h2 className="text-lg font-bold text-slate-200">LLM Telemetry</h2>
        <span className="ml-auto text-xs text-slate-500 font-mono">live · refreshes every 5s</span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {statCards.map(({ icon: Icon, label, value, sub, color }) => (
          <div key={label} className="p-4 bg-slate-900/50 rounded-lg border border-slate-700/50">
            <div className={`flex items-center space-x-1.5 text-xs text-slate-400 mb-2`}>
              <Icon size={13} className={color} /><span>{label}</span>
            </div>
            <div className="text-xl font-bold text-slate-100">{value}</div>
            <div className="text-xs text-slate-500 mt-1">{sub}</div>
          </div>
        ))}
      </div>

      {/* Per-call log */}
      {data.calls && data.calls.length > 0 && (
        <div>
          <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3 flex items-center">
            <Cpu size={12} className="mr-1.5" /> Per-Call Log (last {data.calls.length})
          </h3>
          <div className="overflow-x-auto rounded-lg border border-slate-700/50">
            <table className="w-full text-xs text-left">
              <thead className="bg-slate-900/60 text-slate-400">
                <tr>
                  {['Call Type', 'Model', 'Tokens In', 'Tokens Out', 'Latency', 'Cache'].map(h => (
                    <th key={h} className="px-3 py-2 font-semibold">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/30">
                {data.calls.slice(0, 10).map((call, i) => (
                  <tr key={i} className="hover:bg-slate-700/20">
                    <td className="px-3 py-2 font-mono text-slate-300">{call.call_type}</td>
                    <td className="px-3 py-2 text-slate-400">{call.model}</td>
                    <td className="px-3 py-2 text-slate-400">{call.prompt_tokens}</td>
                    <td className="px-3 py-2 text-slate-400">{call.completion_tokens}</td>
                    <td className="px-3 py-2 text-slate-400">{call.latency_ms.toFixed(0)} ms</td>
                    <td className="px-3 py-2">
                      <span className={`px-1.5 py-0.5 rounded text-xs font-bold ${call.cache_hit ? 'bg-green-500/20 text-green-400' : 'bg-slate-700 text-slate-400'}`}>
                        {call.cache_hit ? 'HIT' : 'MISS'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
