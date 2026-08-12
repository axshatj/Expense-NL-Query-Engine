import React, { useState } from 'react';
import { Search, Sparkles, ArrowRight, CornerDownLeft } from 'lucide-react';

const SAMPLE_QUESTIONS = [
  "How much did I spend on food last month?",
  "Show me my last 5 transactions at Swiggy",
  "Compare my spending this month vs last month",
  "What subscriptions am I paying for?",
  "How much did I spend on travel this year?"
];

export default function QueryConsole({ onExecuteQuery, loading }) {
  const [question, setQuestion] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!question.trim() || loading) return;
    onExecuteQuery(question);
  };

  const handleSelectSample = (sample) => {
    setQuestion(sample);
    onExecuteQuery(sample);
  };

  return (
    <div className="glass-card rounded-2xl p-6 relative overflow-hidden">
      {/* Subtle Glowing Background Accent */}
      <div className="absolute -top-24 -right-24 w-60 h-60 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

      <div className="flex items-center gap-2 mb-3">
        <Sparkles className="w-4 h-4 text-indigo-400" />
        <h2 className="text-sm font-bold uppercase tracking-wider text-indigo-300">Natural Language Console</h2>
      </div>

      <form onSubmit={handleSubmit} className="relative mb-4">
        <div className="relative flex items-center">
          <Search className="w-5 h-5 text-slate-400 absolute left-4 pointer-events-none" />
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask anything about your expenses (e.g. 'How much did I spend on dining last month?')"
            disabled={loading}
            className="w-full pl-12 pr-32 py-4 rounded-xl glass-input text-slate-100 placeholder-slate-500 text-sm focus:outline-none transition-all disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={loading || !question.trim()}
            className="absolute right-2.5 px-4 py-2 rounded-lg bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white text-xs font-semibold flex items-center gap-1.5 transition-all shadow-md shadow-indigo-600/30 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Querying...
              </span>
            ) : (
              <>
                <span>Ask AI</span>
                <CornerDownLeft className="w-3.5 h-3.5" />
              </>
            )}
          </button>
        </div>
      </form>

      {/* Quick Sample Questions Pills */}
      <div>
        <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-2">Try asking:</span>
        <div className="flex flex-wrap gap-2">
          {SAMPLE_QUESTIONS.map((q, idx) => (
            <button
              key={idx}
              onClick={() => handleSelectSample(q)}
              disabled={loading}
              className="text-xs px-3 py-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-700/80 text-slate-300 border border-slate-700/60 hover:border-indigo-500/40 transition-all flex items-center gap-1 hover:text-white"
            >
              <span>"{q}"</span>
              <ArrowRight className="w-3 h-3 text-slate-500 group-hover:text-indigo-400" />
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
