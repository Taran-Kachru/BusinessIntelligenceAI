import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Clock, TrendingUp, AlertTriangle } from 'lucide-react';

export default function DrillIn({ evidence, movement, drivers }) {
  // PVM waterfall mock data based on movement
  const data = [
    { name: 'Starting', value: 100 },
    { name: 'Price', value: 15, fill: '#4ade80' },
    { name: 'Volume', value: -10, fill: '#f87171' },
    { name: 'Mix', value: 5, fill: '#4ade80' },
    { name: 'Ending', value: 110 }
  ];

  return (
    <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-100">
      <div className="flex justify-between items-center mb-6">
        <h3 className="text-xl font-semibold text-gray-800">Evidence Drill-In</h3>
        <div className="flex items-center text-sm text-gray-500">
          <Clock className="w-4 h-4 mr-1" />
          <span>Updated: {evidence?.freshness || 'Just now'}</span>
        </div>
      </div>

      <div className="mb-8">
        <h4 className="text-sm font-medium text-gray-600 mb-4 uppercase tracking-wider">Price/Volume/Mix (PVM) Impact</h4>
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
              <XAxis dataKey="name" tickLine={false} axisLine={false} />
              <YAxis tickLine={false} axisLine={false} />
              <Tooltip cursor={{fill: 'transparent'}} />
              <Bar dataKey="value" fill="#3b82f6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div>
        <h4 className="text-sm font-medium text-gray-600 mb-4 uppercase tracking-wider">Ranked Drivers</h4>
        <div className="space-y-3">
          {(drivers || []).map((driver, idx) => (
            <div key={idx} className="flex items-center justify-between p-3 bg-gray-50 rounded-md">
              <div className="flex items-center">
                <span className="w-6 h-6 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-xs font-bold mr-3">{idx + 1}</span>
                <span className="font-medium text-gray-700">{driver.name}</span>
              </div>
              <div className="flex items-center">
                <span className={`text-sm font-semibold ${driver.impact > 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {driver.impact > 0 ? '+' : ''}{driver.impact}%
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
