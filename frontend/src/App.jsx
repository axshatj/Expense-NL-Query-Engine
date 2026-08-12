import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import StatsOverview from './components/StatsOverview';
import QueryConsole from './components/QueryConsole';
import GroundedResultCard from './components/GroundedResultCard';
import InspectorModal from './components/InspectorModal';
import TransactionTable from './components/TransactionTable';
import SMSIngestModal from './components/SMSIngestModal';

export default function App() {
  const [stats, setStats] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [queryResult, setQueryResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [apiHealth, setApiHealth] = useState(false);
  
  const [showInspector, setShowInspector] = useState(false);
  const [showSMSModal, setShowSMSModal] = useState(false);

  const fetchStats = async () => {
    try {
      const res = await fetch('/api/stats');
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch (err) {
      console.error('Failed to fetch stats:', err);
    }
  };

  const fetchTransactions = async (cat = null) => {
    try {
      const url = cat ? `/api/transactions?limit=50&category=${encodeURIComponent(cat)}` : '/api/transactions?limit=50';
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setTransactions(data);
      }
    } catch (err) {
      console.error('Failed to fetch transactions:', err);
    }
  };

  const checkHealth = async () => {
    try {
      const res = await fetch('/api/health');
      setApiHealth(res.ok);
    } catch (err) {
      setApiHealth(false);
    }
  };

  useEffect(() => {
    checkHealth();
    fetchStats();
    fetchTransactions();
  }, []);

  const handleFilterCategory = (cat) => {
    setSelectedCategory(cat);
    fetchTransactions(cat);
  };

  const handleExecuteQuery = async (questionText) => {
    setLoading(true);
    try {
      const res = await fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: questionText, ref_date: '2026-08-11' }),
      });

      if (res.ok) {
        const data = await res.json();
        setQueryResult(data);
      } else {
        const err = await res.json();
        alert(`Error executing query: ${err.detail || 'Server error'}`);
      }
    } catch (err) {
      alert(`Network error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleIngestSuccess = () => {
    fetchStats();
    fetchTransactions(selectedCategory);
  };

  return (
    <div className="min-h-screen flex flex-col font-sans">
      <Header
        apiHealth={apiHealth}
        stats={stats}
        onOpenSMSModal={() => setShowSMSModal(true)}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        {/* Stats Summary Cards */}
        <StatsOverview stats={stats} />

        {/* Natural Language Query Bar */}
        <QueryConsole
          onExecuteQuery={handleExecuteQuery}
          loading={loading}
        />

        {/* Grounded Result Display */}
        {queryResult && (
          <GroundedResultCard
            result={queryResult}
            onOpenInspector={() => setShowInspector(true)}
          />
        )}

        {/* Transaction History Database */}
        <TransactionTable
          transactions={transactions}
          selectedCategory={selectedCategory}
          onFilterCategory={handleFilterCategory}
        />
      </main>

      {/* Modals */}
      {showInspector && (
        <InspectorModal
          result={queryResult}
          onClose={() => setShowInspector(false)}
        />
      )}

      {showSMSModal && (
        <SMSIngestModal
          onClose={() => setShowSMSModal(false)}
          onIngestSuccess={handleIngestSuccess}
        />
      )}

      {/* Footer */}
      <footer className="border-t border-white/5 py-6 text-center text-xs text-slate-500">
        Expense NL Query Engine &bull; Built with FastAPI, SQLite, Pydantic & React Tailwind
      </footer>
    </div>
  );
}
