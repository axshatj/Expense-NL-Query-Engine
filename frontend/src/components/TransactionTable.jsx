import React, { useState } from 'react';
import { ListFilter, Search, ArrowUpDown } from 'lucide-react';

const CATEGORY_COLORS = {
  dining: 'bg-orange-500/15 text-orange-400 border-orange-500/30',
  groceries: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  shopping: 'bg-purple-500/15 text-purple-400 border-purple-500/30',
  subscriptions: 'bg-indigo-500/15 text-indigo-400 border-indigo-500/30',
  transport: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  entertainment: 'bg-pink-500/15 text-pink-400 border-pink-500/30',
  travel: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30',
  bills_utilities: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
  transfers: 'bg-slate-500/15 text-slate-400 border-slate-500/30',
  healthcare: 'bg-rose-500/15 text-rose-400 border-rose-500/30',
  other: 'bg-gray-500/15 text-gray-400 border-gray-500/30',
};

export default function TransactionTable({ transactions, onFilterCategory, selectedCategory }) {
  const [searchTerm, setSearchTerm] = useState('');

  const filteredTransactions = (transactions || []).filter((tx) => {
    const term = searchTerm.toLowerCase();
    const merchant = (tx.merchant_normalized || tx.merchant_raw || '').toLowerCase();
    const category = (tx.category || '').toLowerCase();
    return merchant.includes(term) || category.includes(term);
  });

  return (
    <div className="glass-card rounded-2xl p-6">
      
      {/* Table Header Controls */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
        <div>
          <h3 className="font-bold text-base text-white">Indexed Transaction Database</h3>
          <p className="text-xs text-slate-400">Normalized merchant strings and taxonomy mapping</p>
        </div>

        <div className="flex items-center gap-3 w-full sm:w-auto">
          {/* Category Selector */}
          <div className="relative">
            <select
              value={selectedCategory || ''}
              onChange={(e) => onFilterCategory(e.target.value || null)}
              className="px-3 py-2 text-xs rounded-xl glass-input text-slate-200 focus:outline-none cursor-pointer"
            >
              <option value="">All Categories</option>
              <option value="dining">Dining</option>
              <option value="groceries">Groceries</option>
              <option value="shopping">Shopping</option>
              <option value="subscriptions">Subscriptions</option>
              <option value="transport">Transport</option>
              <option value="travel">Travel</option>
              <option value="bills_utilities">Bills & Utilities</option>
              <option value="entertainment">Entertainment</option>
              <option value="transfers">Transfers</option>
            </select>
          </div>

          {/* Search Box */}
          <div className="relative flex-1 sm:flex-initial">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search merchant..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9 pr-3 py-1.5 text-xs rounded-xl glass-input text-slate-200 placeholder-slate-500 focus:outline-none w-full sm:w-48"
            />
          </div>
        </div>
      </div>

      {/* Table Container */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs text-slate-300">
          <thead className="bg-slate-900/60 uppercase font-semibold text-[11px] text-slate-400 border-b border-white/10">
            <tr>
              <th className="py-3 px-4">Date</th>
              <th className="py-3 px-4">Normalized Merchant</th>
              <th className="py-3 px-4">Category</th>
              <th className="py-3 px-4 text-right">Amount</th>
              <th className="py-3 px-4">Source</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {filteredTransactions.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-8 text-center text-slate-500 italic">
                  No matching transactions found in database.
                </td>
              </tr>
            ) : (
              filteredTransactions.map((tx, idx) => {
                const badgeStyle = CATEGORY_COLORS[tx.category] || CATEGORY_COLORS.other;
                return (
                  <tr key={tx.id || idx} className="hover:bg-slate-800/40 transition-colors">
                    <td className="py-3.5 px-4 font-mono text-slate-400">{tx.date}</td>
                    <td className="py-3.5 px-4 font-semibold text-white">
                      {tx.merchant_normalized || tx.merchant_raw}
                      {tx.merchant_raw && tx.merchant_raw !== tx.merchant_normalized && (
                        <span className="block text-[10px] text-slate-500 font-normal font-mono truncate max-w-xs">
                          {tx.merchant_raw}
                        </span>
                      )}
                    </td>
                    <td className="py-3.5 px-4">
                      <span className={`px-2.5 py-1 rounded-full text-[10px] font-semibold border ${badgeStyle}`}>
                        {tx.category || 'other'}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-right font-bold text-white font-mono">
                      {tx.transaction_type === 'credit' ? '+' : '-'}₹{Number(tx.amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="px-2 py-0.5 rounded text-[10px] uppercase font-semibold bg-slate-800 text-slate-400 border border-slate-700">
                        {tx.source || 'sms'}
                      </span>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

    </div>
  );
}
