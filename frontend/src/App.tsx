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
      <div style={{
        display: 'flex',
        flexDirection: 'row',
        maxWidth: 1100,
        margin: '2.5rem auto',
        fontFamily: '"Inter", "Noto Sans JP", sans-serif',
        gap: 36,
        background: '#f8fafd',
        borderRadius: 16,
        boxShadow: '0 4px 24px rgba(0,0,0,0.08)',
        padding: '28px 24px',
        border: '2px solid #e0e3e8',
      }}>
        {/* 左カラム: コード＋標準入力＋実行ボタン */}
        <div style={{
          flex: 1,
          minWidth: 0,
          display: 'flex',
          flexDirection: 'column',
          gap: 18,
          background: '#fff',
          borderRadius: 12,
          boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
          border: '2px solid #e0e3e8',
          padding: '16px 12px',
        }}>
          <h2 style={{ fontWeight: 700, fontSize: 26, color: '#222', marginBottom: 8 }}>オンラインコード実行</h2>
          <CodeEditor
            language={language}
            code={code}
            onLanguageChange={setLanguage}
            onCodeChange={setCode}
          />
          <StdinInput stdin={stdin} onStdinChange={setStdin} />
          <div style={{ margin: '18px 0 0 0', textAlign: 'right' }}>
            <button
              onClick={runCode}
              disabled={loading}
              style={{
                fontSize: 18,
                padding: '10px 36px',
                background: loading ? '#aaa' : 'linear-gradient(90deg,#4f8cff,#38c7ff)',
                color: '#fff',
                border: 'none',
                borderRadius: 8,
                fontWeight: 600,
                boxShadow: '0 2px 8px rgba(0,0,0,0.07)',
                cursor: loading ? 'not-allowed' : 'pointer',
                transition: 'background 0.2s',
              }}>
              {loading ? '実行中...' : '実行'}
            </button>
          </div>
        </div>
        {/* 右カラム: 出力エリア＋メタ情報 */}
        <div style={{
          flex: 1,
          minWidth: 0,
          display: 'flex',
          flexDirection: 'column',
          gap: 18,
          background: '#fff',
          borderRadius: 12,
          boxShadow: '0 2px 8px rgba(0,0,0,0.04)',
          border: '2px solid #e0e3e8',
          padding: '16px 12px',
        }}>
          <h3 style={{ fontWeight: 700, fontSize: 20, color: '#222', marginBottom: 8 }}>出力</h3>
          <div style={{
            background: 'linear-gradient(90deg,#222 80%,#444 100%)',
            color: '#eee',
            borderRadius: 10,
            padding: 16,
            minHeight: 180,
            fontSize: 16,
            fontFamily: 'monospace',
            boxShadow: '0 2px 8px rgba(0,0,0,0.10)',
            border: '2px solid #e0e3e8',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-all',
          }}>
            {/* 初期から表示。エラー優先、なければ標準出力 */}
            {result?.stderr ? (
              <pre style={{ color: '#ff6b6b', margin: 0, background: 'none', fontSize: 17 }}>{result.stderr}</pre>
            ) : (
              <pre style={{ color: '#38ffb3', margin: 0, background: 'none', fontSize: 17 }}>{result?.stdout ?? ''}</pre>
            )}
          </div>
          {/* メタ情報（終了コード・実行時間）を分離表示 */}
          <div style={{
            marginTop: 8,
            fontSize: 15,
            color: '#555',
            background: '#f7f7f7',
            borderRadius: 10,
            padding: '8px 14px',
            boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
            display: 'flex',
            flexDirection: 'row',
            gap: 32,
            alignItems: 'center',
            fontWeight: 500,
            border: '2px solid #e0e3e8',
          }}>
            <div><b>終了コード:</b> <span style={{ color: '#007aff' }}>{result?.exit_code ?? '-'}</span></div>
            <div><b>実行時間:</b> <span style={{ color: '#007aff' }}>{result?.time ?? '-'} 秒</span></div>
          </div>
        </div>
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
      const apiUrl = `http://${window.location.hostname}:8000/run`;
      const res = await fetch(apiUrl, {
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