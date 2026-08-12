import React, { useState } from 'react';
import { X, MessageSquarePlus, Sparkles, CheckCircle2 } from 'lucide-react';

const SAMPLE_SMS = [
  "Spent Rs.450.00 at SWIGGY INDIA on HDFC Bank Card ending 1234 on 05-AUG-26. Avbl Bal: Rs.45,200.00",
  "Amt Debited INR 2,499.00 from A/C XX9876 to NETFLIX RECURRING on 01-AUG-26.",
  "UPI Ref: 421900123. Rs.1,200.00 debited for ZOMATO ORDER on 10-AUG-26.",
  "Paid Rs 3,500.00 at HPCL PETROL PUMP on SBI Card ending 5544 on 08-AUG-26."
];

export default function SMSIngestModal({ onClose, onIngestSuccess }) {
  const [smsText, setSmsText] = useState(SAMPLE_SMS[0]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!smsText.trim() || loading) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch('/api/ingest/sms', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sms_text: smsText }),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Failed to parse SMS');
      }

      const data = await res.json();
      setResult(data);
      if (onIngestSuccess) onIngestSuccess();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md animate-fade-in">
      <div className="glass-card w-full max-w-xl rounded-2xl overflow-hidden shadow-2xl border border-white/10 flex flex-col">
        
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-white/10 flex items-center justify-between bg-slate-900/60">
          <div className="flex items-center gap-2">
            <MessageSquarePlus className="w-5 h-5 text-violet-400" />
            <h3 className="font-bold text-base text-white">SMS Parser & Normalizer Ingest</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-all"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
              Paste Raw SMS Text Body:
            </label>
            <textarea
              rows={4}
              value={smsText}
              onChange={(e) => setSmsText(e.target.value)}
              className="w-full p-3 rounded-xl glass-input text-slate-100 placeholder-slate-500 text-xs font-mono focus:outline-none"
              placeholder="e.g. Spent Rs.450 at Swiggy on 05-AUG-26..."
            />
          </div>

          {/* Quick Preset Samples */}
          <div>
            <span className="text-[11px] text-slate-400 block mb-1.5">Or try sample bank SMS:</span>
            <div className="flex flex-wrap gap-1.5">
              {SAMPLE_SMS.map((sample, i) => (
                <button
                  type="button"
                  key={i}
                  onClick={() => setSmsText(sample)}
                  className="text-[10px] px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700"
                >
                  Sample #{i + 1}
                </button>
              ))}
            </div>
          </div>

          {error && (
            <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
              {error}
            </div>
          )}

          {result && (
            <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs space-y-1">
              <div className="flex items-center gap-1.5 font-bold text-emerald-400">
                <CheckCircle2 className="w-4 h-4" />
                <span>Successfully Parsed & Normalized!</span>
              </div>
              <p><strong>Merchant:</strong> {result.transaction.merchant_normalized} ({result.transaction.merchant_raw})</p>
              <p><strong>Amount:</strong> ₹{result.transaction.amount}</p>
              <p><strong>Category:</strong> {result.transaction.category}</p>
              <p><strong>Date:</strong> {result.transaction.date}</p>
            </div>
          )}

          <div className="pt-2 flex justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold"
            >
              Close
            </button>
            <button
              type="submit"
              disabled={loading || !smsText.trim()}
              className="px-5 py-2 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white text-xs font-semibold flex items-center gap-1.5 shadow-md shadow-violet-600/30"
            >
              {loading ? 'Processing...' : 'Parse & Ingest SMS'}
            </button>
          </div>
        </form>

      </div>
    </div>
  );
}
