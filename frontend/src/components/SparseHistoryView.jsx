import React from 'react';
import { Info, TrendingDown } from 'lucide-react';

export default function SparseHistoryView({ sku, dataPoints, originalConfidence, newConfidence }) {
  return (
    <div className="bg-amber-50 border-l-4 border-amber-500 p-4 rounded-r-lg shadow-sm mb-6">
      <div className="flex items-start">
        <div className="flex-shrink-0 mt-0.5">
          <Info className="w-5 h-5 text-amber-500" />
        </div>
        <div className="ml-3 w-full">
          <h3 className="text-sm font-medium text-amber-800">Sparse History Detected</h3>
          <div className="mt-2 text-sm text-amber-700">
            <p>
              The product <strong>{sku || 'Unknown'}</strong> is newly launched and only has {dataPoints || 0} historical data points available.
            </p>
          </div>
          <div className="mt-4 flex items-center bg-white/60 p-3 rounded-md w-max border border-amber-200">
            <div className="text-center px-4 border-r border-amber-200">
              <div className="text-xs text-gray-500 mb-1">Initial Confidence</div>
              <div className="font-semibold text-gray-700">{originalConfidence || 85}%</div>
            </div>
            <div className="px-4 flex items-center text-amber-600">
              <TrendingDown className="w-4 h-4 mr-2" />
              <div className="text-center">
                <div className="text-xs text-amber-600/80 mb-1">Adjusted Confidence</div>
                <div className="font-bold text-amber-800">{newConfidence || 45}%</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
