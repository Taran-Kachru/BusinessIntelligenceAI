import React, { useState, useEffect } from 'react';
import { Bot, Quote } from 'lucide-react';

export default function NarrativePanel({ queryId }) {
  const [narratives, setNarratives] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Mock fetch logic connecting to FastAPI backend
    const fetchNarrative = async () => {
      try {
        // const res = await fetch(`/api/insight/narrative?query_id=${queryId}`);
        // const data = await res.json();
        
        // Simulating API response
        setTimeout(() => {
          setNarratives({
            ceo: "Total revenue grew by 10% driven by strong pricing realization (+15%) despite volume headwinds (-10%) in the APAC region.",
            rm: "APAC volumes dropped 10% mainly due to the recent price hike and aggressive competitor promotions in Q2.",
            model: "claude-sonnet-5"
          });
          setLoading(false);
        }, 800);
      } catch (e) {
        console.error(e);
      }
    };
    
    fetchNarrative();
  }, [queryId]);

  if (loading) return <div className="animate-pulse h-32 bg-gray-100 rounded-lg"></div>;

  return (
    <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-100">
      <div className="flex justify-between items-center mb-6">
        <h3 className="text-xl font-semibold text-gray-800">Synthesized Narratives</h3>
        <div className="flex items-center bg-purple-50 text-purple-700 px-3 py-1 rounded-full text-xs font-medium border border-purple-100">
          <Bot className="w-3 h-3 mr-1" />
          <span>Computed by: {narratives.model}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-blue-50/50 p-5 rounded-lg border border-blue-100">
          <h4 className="text-sm font-semibold text-blue-800 mb-3 uppercase tracking-wider">Executive Summary (CEO)</h4>
          <p className="text-gray-700 leading-relaxed text-sm">
            {narratives.ceo.split(/(10%|\+15%|-10%)/).map((part, i) => 
              part.includes('%') ? <span key={i} className="bg-yellow-200/50 px-1 rounded font-medium border-b border-yellow-300">{part}</span> : part
            )}
          </p>
        </div>
        
        <div className="bg-green-50/50 p-5 rounded-lg border border-green-100">
          <h4 className="text-sm font-semibold text-green-800 mb-3 uppercase tracking-wider">Operational View (Reg. Manager)</h4>
          <p className="text-gray-700 leading-relaxed text-sm">
             {narratives.rm.split(/(10%)/).map((part, i) => 
              part.includes('%') ? <span key={i} className="bg-yellow-200/50 px-1 rounded font-medium border-b border-yellow-300">{part}</span> : part
            )}
          </p>
        </div>
      </div>
    </div>
  );
}
