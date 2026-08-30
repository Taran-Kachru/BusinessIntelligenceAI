import React, { useState, useEffect } from 'react';
import { ThumbsUp, ThumbsDown, MessageSquare, Check, X } from 'lucide-react';

export default function FeedbackWidget({ insightId, context }) {
  const [feedback, setFeedback] = useState(null);
  const [correction, setCorrection] = useState('');
  const [showCorrection, setShowCorrection] = useState(false);
  const [queue, setQueue] = useState([]);
  const [viewQueue, setViewQueue] = useState(false);

  useEffect(() => {
    if (viewQueue) {
      fetch('/api/feedback/queue')
        .then(res => res.json())
        .then(data => setQueue(data))
        .catch(err => console.error("Error fetching queue:", err));
    }
  }, [viewQueue]);

  const submitFeedback = async (type) => {
    setFeedback(type);
    if (type === 'down') setShowCorrection(true);
    
    await fetch('/api/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ insightId, type, correction })
    });
  };

  const submitCorrection = async () => {
    await fetch('/api/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ insightId, type: 'correction', correction })
    });
    setShowCorrection(false);
  };

  return (
    <div className="p-4 bg-white shadow rounded-lg border border-gray-200">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-800">Insight Feedback</h3>
        <button 
          onClick={() => setViewQueue(!viewQueue)}
          className="text-sm text-blue-600 hover:underline"
        >
          {viewQueue ? 'Hide Queue' : 'View Pending Queue'}
        </button>
      </div>

      <div className="flex items-center space-x-4 mb-4">
        <button 
          onClick={() => submitFeedback('up')}
          className={`p-2 rounded-full ${feedback === 'up' ? 'bg-green-100 text-green-600' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
        >
          <ThumbsUp size={20} />
        </button>
        <button 
          onClick={() => submitFeedback('down')}
          className={`p-2 rounded-full ${feedback === 'down' ? 'bg-red-100 text-red-600' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
        >
          <ThumbsDown size={20} />
        </button>
      </div>

      {showCorrection && (
        <div className="mt-4 flex space-x-2">
          <input 
            type="text" 
            value={correction}
            onChange={(e) => setCorrection(e.target.value)}
            placeholder="Suggest a correction..."
            className="flex-1 p-2 border rounded-md"
          />
          <button 
            onClick={submitCorrection}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            Submit
          </button>
        </div>
      )}

      {viewQueue && (
        <div className="mt-6 border-t pt-4">
          <h4 className="text-md font-medium text-gray-700 mb-2">Pending Validation Queue</h4>
          {queue.length === 0 ? (
            <p className="text-sm text-gray-500">No pending items.</p>
          ) : (
            <ul className="space-y-2">
              {queue.map((item, idx) => (
                <li key={idx} className="p-3 bg-gray-50 rounded border text-sm flex justify-between items-center">
                  <div>
                    <span className="font-semibold">{item.insightId}</span> - {item.type}
                    {item.correction && <p className="text-gray-600 mt-1 italic">"{item.correction}"</p>}
                  </div>
                  <div className="flex space-x-2">
                    <button className="text-green-600"><Check size={16} /></button>
                    <button className="text-red-600"><X size={16} /></button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
