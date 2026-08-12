import React, { useState } from 'react';
import { X, Code2, Database, Layers, Copy, Check } from 'lucide-react';

export default function InspectorModal({ result, onClose }) {
  const [activeTab, setActiveTab] = useState('ir');
  const [copied, setCopied] = useState(false);

  if (!result) return null;

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getActiveContent = () => {
    if (activeTab === 'ir') {
      return JSON.stringify(result.ir, null, 2);
    } else if (activeTab === 'sql') {
      const sqlObj = result.db_result?.query_sql || result.db_result?.primary_period?.sql || result.db_result;
      return typeof sqlObj === 'string' ? sqlObj : JSON.stringify(sqlObj, null, 2);
    } else if (activeTab === 'data') {
      return JSON.stringify(result.db_result, null, 2);
    }
    return '';
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md animate-fade-in">
      <div className="glass-card w-full max-w-4xl rounded-2xl overflow-hidden shadow-2xl border border-white/10 flex flex-col max-h-[85vh]">
        
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-white/10 flex items-center justify-between bg-slate-900/60">
          <div className="flex items-center gap-2">
            <Code2 className="w-5 h-5 text-indigo-400" />
            <h3 className="font-bold text-base text-white">Pipeline Execution Inspector</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-all"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="px-6 pt-3 bg-slate-900/40 border-b border-white/5 flex items-center justify-between">
          <div className="flex gap-2">
            <button
              onClick={() => setActiveTab('ir')}
              className={`px-4 py-2 text-xs font-semibold rounded-t-lg transition-all border-b-2 flex items-center gap-1.5 ${
                activeTab === 'ir'
                  ? 'border-indigo-500 bg-slate-800/80 text-indigo-300'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <Layers className="w-4 h-4" />
              <span>Stage 1: JSON IR</span>
            </button>
            <button
              onClick={() => setActiveTab('sql')}
              className={`px-4 py-2 text-xs font-semibold rounded-t-lg transition-all border-b-2 flex items-center gap-1.5 ${
                activeTab === 'sql'
                  ? 'border-indigo-500 bg-slate-800/80 text-indigo-300'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <Database className="w-4 h-4" />
              <span>Stage 2: Parameterized SQL</span>
            </button>
            <button
              onClick={() => setActiveTab('data')}
              className={`px-4 py-2 text-xs font-semibold rounded-t-lg transition-all border-b-2 flex items-center gap-1.5 ${
                activeTab === 'data'
                  ? 'border-indigo-500 bg-slate-800/80 text-indigo-300'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <Code2 className="w-4 h-4" />
              <span>DB Output Payload</span>
            </button>
          </div>

          <button
            onClick={() => copyToClipboard(getActiveContent())}
            className="px-3 py-1 text-xs rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 flex items-center gap-1 border border-slate-700 transition-all mb-2"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copied ? 'Copied' : 'Copy'}</span>
          </button>
        </div>

        {/* Code Content Box */}
        <div className="p-6 overflow-y-auto font-mono text-xs text-indigo-200 bg-slate-950/90 leading-relaxed flex-1">
          <pre>{getActiveContent()}</pre>
        </div>

      </div>
    </div>
  );
}
