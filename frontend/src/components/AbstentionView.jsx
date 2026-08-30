import React from 'react';
import { HelpCircle, AlertOctagon } from 'lucide-react';

export default function AbstentionView({ confidence, reason, clarifyingQuestion }) {
  return (
    <div className="bg-white border-2 border-dashed border-gray-300 rounded-lg p-8 text-center max-w-2xl mx-auto my-8">
      <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gray-100 text-gray-500 mb-4">
        <AlertOctagon className="w-8 h-8" />
      </div>
      
      <h3 className="text-xl font-semibold text-gray-800 mb-2">Analysis Abstained</h3>
      <div className="inline-block bg-red-100 text-red-700 px-3 py-1 rounded-full text-xs font-bold mb-6">
        Low Confidence Score: {confidence}%
      </div>
      
      <p className="text-gray-600 mb-8 max-w-md mx-auto">
        {reason || "The system does not have sufficient reliable evidence to generate a definitive narrative or action plan for this scenario."}
      </p>
      
      <div className="bg-blue-50 border border-blue-100 rounded-lg p-5 text-left">
        <div className="flex items-start">
          <HelpCircle className="w-5 h-5 text-blue-600 mt-0.5 mr-3 flex-shrink-0" />
          <div>
            <h4 className="font-medium text-blue-900 mb-1">Clarification Needed</h4>
            <p className="text-sm text-blue-800">
              {clarifyingQuestion || "Could you specify if the Q2 promotional data includes the mid-quarter flash sale?"}
            </p>
            <div className="mt-4 flex gap-2">
              <button className="bg-blue-600 text-white px-4 py-2 rounded text-sm font-medium hover:bg-blue-700 transition-colors">
                Provide Answer
              </button>
              <button className="bg-white text-blue-600 border border-blue-200 px-4 py-2 rounded text-sm font-medium hover:bg-blue-50 transition-colors">
                Skip Analysis
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
