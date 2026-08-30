import React, { useState, useEffect } from 'react';
import { AlertTriangle, CheckCircle, ArrowRight, ShieldAlert } from 'lucide-react';

export default function ActionCards({ insightId, userAuthorityLevel = 2 }) {
  const [actions, setActions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Mock fetch connecting to FastAPI backend
    const fetchActions = async () => {
      // const res = await fetch(`/api/insight/actions?insight_id=${insightId}`);
      // const data = await res.json();
      
      setTimeout(() => {
        setActions([
          {
            id: 1,
            title: "Adjust Q3 Promotional Spend",
            description: "Reallocate $50k from trade spend to direct consumer promos in APAC to counter volume drop.",
            owner: "APAC Sales Director",
            requiredAuthority: 3, // higher than user
            impact: "Medium",
            effort: "Low",
            status: "Pending"
          },
          {
            id: 2,
            title: "Review Pricing Strategy",
            description: "Analyze price elasticity across top 5 SKUs.",
            owner: "Pricing Analyst",
            requiredAuthority: 1,
            impact: "High",
            effort: "High",
            status: "Draft"
          }
        ]);
        setLoading(false);
      }, 600);
    };
    
    fetchActions();
  }, [insightId]);

  if (loading) return <div className="animate-pulse h-40 bg-gray-100 rounded-lg"></div>;

  return (
    <div className="space-y-4">
      <h3 className="text-xl font-semibold text-gray-800 mb-4">Recommended Actions</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {actions.map(action => {
          const needsEscalation = action.requiredAuthority > userAuthorityLevel;
          
          return (
            <div key={action.id} className="bg-white border border-gray-200 rounded-lg overflow-hidden shadow-sm hover:shadow-md transition-shadow">
              <div className="p-5">
                <div className="flex justify-between items-start mb-2">
                  <h4 className="font-semibold text-gray-900">{action.title}</h4>
                  <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                    action.impact === 'High' ? 'bg-red-100 text-red-700' : 'bg-yellow-100 text-yellow-700'
                  }`}>
                    {action.impact} Impact
                  </span>
                </div>
                
                <p className="text-sm text-gray-600 mb-4">{action.description}</p>
                
                <div className="grid grid-cols-2 gap-y-2 text-sm">
                  <div>
                    <span className="text-gray-500">Owner: </span>
                    <span className="font-medium text-gray-800">{action.owner}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Effort: </span>
                    <span className="font-medium text-gray-800">{action.effort}</span>
                  </div>
                </div>
              </div>
              
              <div className="bg-gray-50 px-5 py-3 border-t border-gray-100 flex justify-between items-center">
                {needsEscalation ? (
                  <div className="flex items-center text-amber-600 text-xs font-medium bg-amber-50 px-2 py-1 rounded border border-amber-200">
                    <ShieldAlert className="w-3 h-3 mr-1" />
                    Requires Escalation (L{action.requiredAuthority})
                  </div>
                ) : (
                  <div className="flex items-center text-green-600 text-xs font-medium">
                    <CheckCircle className="w-3 h-3 mr-1" />
                    Within Authority
                  </div>
                )}
                
                <button className="text-blue-600 hover:text-blue-800 text-sm font-medium flex items-center">
                  Review <ArrowRight className="w-4 h-4 ml-1" />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
