import React, { useState } from 'react';
import { Send, FileText, Search, Loader2 } from 'lucide-react';

export default function AskBox({ userContext }) {
  const [query, setQuery] = useState('');
  const [response, setResponse] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    try {
      const res = await fetch('/api/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, context: userContext })
      });
      const data = await res.json();
      setResponse(data);
    } catch (err) {
      console.error("Error asking question:", err);
      setResponse({ error: 'Failed to fetch response.' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 bg-white shadow rounded-lg border border-gray-200 flex flex-col h-full">
      <div className="flex items-center space-x-2 mb-4">
        <Search className="text-blue-600" size={20} />
        <h2 className="text-lg font-bold text-gray-800">Ask the Data</h2>
      </div>

      <div className="flex-1 overflow-y-auto mb-4 min-h-[200px] border rounded-lg p-4 bg-gray-50">
        {loading ? (
          <div className="flex items-center justify-center h-full text-gray-500">
            <Loader2 className="animate-spin mr-2" size={24} /> Processing...
          </div>
        ) : response ? (
          <div className="space-y-4">
            {response.error ? (
              <div className="text-red-500">{response.error}</div>
            ) : (
              <>
                <div className="prose prose-sm max-w-none text-gray-800">
                  {response.answer}
                </div>
                
                {response.citations && response.citations.length > 0 && (
                  <div className="mt-4 pt-4 border-t border-gray-200">
                    <h4 className="text-sm font-semibold text-gray-600 flex items-center mb-2">
                      <FileText size={16} className="mr-1" /> Evidence & Citations
                    </h4>
                    <ul className="space-y-2">
                      {response.citations.map((cite, idx) => (
                        <li key={idx} className="text-xs bg-white p-2 rounded border border-gray-200 text-gray-600 shadow-sm">
                          <span className="font-semibold text-blue-600">[{idx + 1}] {cite.source}</span>: "{cite.snippet}"
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            )}
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-gray-400 italic">
            Ask a free-text question about your KPIs...
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit} className="flex space-x-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g., Why did Q3 revenue drop in EMEA?"
          className="flex-1 p-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="p-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors flex items-center justify-center"
        >
          <Send size={20} />
        </button>
      </form>
    </div>
  );
}
