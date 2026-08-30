import React, { useState, useEffect } from 'react';
import { Shield, AlertOctagon, Lock } from 'lucide-react';

export default function SecurityTab({ userContext }) {
  const [accessLog, setAccessLog] = useState([]);

  useEffect(() => {
    fetch('/api/security/access-log')
      .then(res => res.json())
      .then(data => setAccessLog(data))
      .catch(err => console.error("Error fetching access log:", err));
  }, []);

  return (
    <div className="p-6 bg-white shadow rounded-lg border border-gray-200">
      <div className="flex items-center space-x-2 mb-6">
        <Shield className="text-blue-600" size={24} />
        <h2 className="text-xl font-bold text-gray-800">Security & Access Logs</h2>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm whitespace-nowrap">
          <thead className="uppercase tracking-wider border-b-2 border-gray-200 bg-gray-50">
            <tr>
              <th className="px-6 py-3 border-b border-gray-200 text-gray-600 font-semibold">Timestamp</th>
              <th className="px-6 py-3 border-b border-gray-200 text-gray-600 font-semibold">User / Role</th>
              <th className="px-6 py-3 border-b border-gray-200 text-gray-600 font-semibold">Action</th>
              <th className="px-6 py-3 border-b border-gray-200 text-gray-600 font-semibold">Query / Resource</th>
              <th className="px-6 py-3 border-b border-gray-200 text-gray-600 font-semibold">Status</th>
            </tr>
          </thead>
          <tbody>
            {accessLog.map((log, index) => {
              const isBlocked = log.status === 'blocked';
              const isRedacted = log.containsPII && userContext?.role !== 'admin';

              return (
                <tr key={index} className={`border-b border-gray-200 hover:bg-gray-50 ${isBlocked ? 'bg-red-50' : ''}`}>
                  <td className="px-6 py-4 text-gray-700">{new Date(log.timestamp).toLocaleString()}</td>
                  <td className="px-6 py-4 text-gray-700">
                    {log.user} <span className="text-xs text-gray-500">({log.role})</span>
                  </td>
                  <td className="px-6 py-4 text-gray-700">{log.action}</td>
                  <td className="px-6 py-4">
                    {isRedacted ? (
                      <div className="flex items-center space-x-1 text-yellow-600">
                        <Lock size={14} />
                        <span className="italic">[REDACTED PII]</span>
                      </div>
                    ) : (
                      <span className="text-gray-800">{log.query}</span>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    {isBlocked ? (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                        <AlertOctagon size={12} className="mr-1" /> Blocked
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                        Allowed
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
