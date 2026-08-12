import React from 'react';
import { ShieldCheck, ShieldAlert, Code2, Clock, CheckCircle2, AlertTriangle } from 'lucide-react';

export default function GroundedResultCard({ result, onOpenInspector }) {
  if (!result) return null;

  const isGrounded = result.is_grounded;
  const fallbackUsed = result.fallback_used;

  return (
    <div className="glass-card rounded-2xl p-6 relative overflow-hidden border-l-4 border-l-indigo-500">
      
      {/* Header Bar with Verification Badges */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4 pb-4 border-b border-white/10">
        <div className="flex items-center gap-2">
          {isGrounded ? (
            <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>Grounded in DB Data</span>
            </span>
          ) : (
            <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-400 border border-amber-500/30 flex items-center gap-1.5">
              <ShieldAlert className="w-4 h-4 text-amber-400" />
              <span>Verification Fallback Triggered</span>
            </span>
          )}

          {fallbackUsed && (
            <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-800 text-slate-300 border border-slate-700 flex items-center gap-1">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
              <span>Templated Fallback</span>
            </span>
          )}
        </div>

        {/* Latency Pill & Inspector Button */}
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-400 flex items-center gap-1">
            <Clock className="w-3.5 h-3.5" />
            <span>{result.latency_ms} ms</span>
          </span>

          <button
            onClick={onOpenInspector}
            className="px-3 py-1.5 rounded-lg bg-indigo-950/60 hover:bg-indigo-900/60 text-indigo-300 border border-indigo-700/50 text-xs font-semibold flex items-center gap-1.5 transition-all shadow-sm"
          >
            <Code2 className="w-4 h-4 text-indigo-400" />
            <span>Inspect Pipeline IR & SQL</span>
          </button>
        </div>
      </div>

      {/* Original Question */}
      <div className="mb-2">
        <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Question</span>
        <p className="text-sm font-medium text-slate-200">"{result.question}"</p>
      </div>

      {/* Grounded Natural Language Answer */}
      <div className="bg-slate-900/80 rounded-xl p-4 border border-slate-800">
        <span className="text-[11px] font-semibold text-indigo-400 uppercase tracking-wider block mb-1.5">Grounded Answer</span>
        <p className="text-base font-semibold text-white leading-relaxed">{result.answer}</p>
      </div>

    </div>
  );
}
