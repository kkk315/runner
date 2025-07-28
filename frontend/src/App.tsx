import React, { useState } from 'react';
import CodeEditor from './components/CodeEditor.tsx';
import StdinInput from './components/StdinInput';
import Layout from './components/Layout';
import ResultPanel from './components/ResultPanel';
import './App.css';

interface CodeResult {
  stdout?: string;
  stderr?: string;
  exit_code?: number;
  time?: number;
  debug?: any;
}


function renderTemplate(params: {
  language: string;
  code: string;
  stdin: string;
  result: CodeResult | null;
  loading: boolean;
  setLanguage: (lang: string) => void;
  setCode: (code: string) => void;
  setStdin: (stdin: string) => void;
  runCode: () => void;
}) {
  const { language, code, stdin, result, loading, setLanguage, setCode, setStdin, runCode } = params;
  return (
    <Layout>
      <div className="App" style={{ maxWidth: 700, margin: '2rem auto', fontFamily: 'sans-serif' }}>
        <h2>オンラインコード実行</h2>
        <CodeEditor
          language={language}
          code={code}
          onLanguageChange={setLanguage}
          onCodeChange={setCode}
        />
        <StdinInput stdin={stdin} onStdinChange={setStdin} />
        <div style={{ margin: '16px 0' }}>
          <button onClick={runCode} disabled={loading} style={{ fontSize: 18, padding: '8px 24px' }}>
            {loading ? '実行中...' : '実行'}
          </button>
        </div>
        <ResultPanel result={result} />
      </div>
    </Layout>
  );
}

function App() {
  const [language, setLanguage] = useState('python');
  const [code, setCode] = useState('print("Hello, world!")');
  const [stdin, setStdin] = useState('');
  const [result, setResult] = useState<CodeResult | null>(null);
  const [loading, setLoading] = useState(false);

  const runCode = async () => {
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch('http://localhost:8000/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ language, code, stdin })
      });
      const data = await res.json();
      setResult(data);
    } catch (e) {
      setResult({ stderr: String(e) });
    }
    setLoading(false);
  };

  return renderTemplate({
    language,
    code,
    stdin,
    result,
    loading,
    setLanguage,
    setCode,
    setStdin,
    runCode,
  });
}

export default App;