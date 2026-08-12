import React from 'react';
import { IndianRupee, Hash, Calendar, PieChart } from 'lucide-react';

export default function StatsOverview({ stats }) {
  if (!stats) return null;

  const totalSpentFormatted = `₹${(stats.total_spent || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      
      {/* Total Spent Card */}
      <div className="glass-card glass-card-hover rounded-2xl p-5 relative overflow-hidden">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Total Spent</span>
          <div className="p-2 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            <IndianRupee className="w-5 h-5" />
          </div>
        </div>
        <div className="text-2xl font-extrabold text-white tracking-tight">{totalSpentFormatted}</div>
        <span className="text-[11px] text-slate-400 mt-1 block">Debits excluding transfers</span>
      </div>

      {/* Total Transactions Card */}
      <div className="glass-card glass-card-hover rounded-2xl p-5 relative overflow-hidden">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Transactions</span>
          <div className="p-2 rounded-xl bg-violet-500/10 text-violet-400 border border-violet-500/20">
            <Hash className="w-5 h-5" />
          </div>
        </div>
        <div className="text-2xl font-extrabold text-white tracking-tight">{stats.total_transactions || 0}</div>
        <span className="text-[11px] text-slate-400 mt-1 block">Normalized SMS & AA rows</span>
      </div>

      {/* Date Range Card */}
      <div className="glass-card glass-card-hover rounded-2xl p-5 relative overflow-hidden">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Date Range</span>
          <div className="p-2 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <Calendar className="w-5 h-5" />
          </div>
        </div>
        <div className="text-sm font-bold text-white tracking-tight mt-1">
          {stats.min_date || 'N/A'} <span className="text-slate-500 font-normal">to</span> {stats.max_date || 'N/A'}
        </div>
        <span className="text-[11px] text-slate-400 mt-1 block">Indexed transaction timeframe</span>
      </div>

      {/* Active Categories Card */}
      <div className="glass-card glass-card-hover rounded-2xl p-5 relative overflow-hidden">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Categories</span>
          <div className="p-2 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <PieChart className="w-5 h-5" />
          </div>
        </div>
        <div className="text-2xl font-extrabold text-white tracking-tight">
          {stats.category_breakdown?.length || 0}
        </div>
        <span className="text-[11px] text-slate-400 mt-1 block">Taxonomy categories mapped</span>
      </div>

    </div>
  );
}
