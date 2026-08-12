import React from 'react';
import { Bot, ShieldCheck, Database, MessageSquarePlus, Sparkles } from 'lucide-react';

export default function Header({ apiHealth, onOpenSMSModal, stats }) {
  return (
    <header className="border-b border-white/10 glass-card sticky top-0 z-40 bg-[#090d16]/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        
        {/* Brand Logo & Name */}
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-gradient-to-tr from-indigo-600 via-violet-600 to-purple-500 shadow-lg shadow-indigo-500/20 text-white">
            <Bot className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-extrabold text-lg text-white tracking-tight">Expense RAG Engine</h1>
              <span className="px-2 py-0.5 text-[10px] font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 rounded-full flex items-center gap-1">
                <Sparkles className="w-3 h-3 text-indigo-400" /> Grounded AI
              </span>
            </div>
            <p className="text-xs text-slate-400">Deterministic NL query & anti-hallucination guardrails</p>
          </div>
        </div>

        {/* Status Badges & Action Buttons */}
        <div className="flex items-center gap-3">
          {/* API Health Pill */}
          <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-800/80 border border-slate-700/60 text-xs">
            <span className={`w-2 h-2 rounded-full ${apiHealth ? 'bg-emerald-400 animate-pulse' : 'bg-rose-500'}`}></span>
            <span className="text-slate-300 font-medium">{apiHealth ? 'API Connected' : 'API Offline'}</span>
          </div>

          {/* Transaction Count Pill */}
          {stats && (
            <div className="hidden md:flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-indigo-950/40 border border-indigo-800/40 text-xs text-indigo-300">
              <Database className="w-3.5 h-3.5" />
              <span>{stats.total_transactions || 0} Transactions</span>
            </div>
          )}

          {/* SMS Ingest Modal Button */}
          <button
            onClick={onOpenSMSModal}
            className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition-all hover:border-slate-600 shadow-sm"
          >
            <MessageSquarePlus className="w-4 h-4 text-violet-400" />
            <span>Parse Raw SMS</span>
          </button>
        </div>

      </div>
    </header>
  );
}
