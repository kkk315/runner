
import React, { useState } from 'react';
import './App.css';

function App() {
  const [language, setLanguage] = useState('python');
  const [code, setCode] = useState('print("Hello, world!")');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const runCode = async () => {
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch('http://localhost:8000/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ language, code })
      });
      const data = await res.json();
      setResult(data);
    } catch (e) {
      setResult({ stderr: String(e) });
    }
    setLoading(false);
  };

  return (
    <div className="App" style={{ maxWidth: 700, margin: '2rem auto', fontFamily: 'sans-serif' }}>
      <h2>オンラインコード実行</h2>
      <div style={{ marginBottom: 16 }}>
        <label>
          言語:
          <select value={language} onChange={e => setLanguage(e.target.value)} style={{ marginLeft: 8 }}>
            <option value="python">Python</option>
            <option value="node">Node.js</option>
          </select>
        </label>
      </div>
      <textarea
        rows={10}
        style={{ width: '100%', fontFamily: 'monospace', fontSize: 16 }}
        value={code}
        onChange={e => setCode(e.target.value)}
      />
      <div style={{ margin: '16px 0' }}>
        <button onClick={runCode} disabled={loading} style={{ fontSize: 18, padding: '8px 24px' }}>
          {loading ? '実行中...' : '実行'}
        </button>
      </div>
      {result && (
        <div style={{ background: '#222', color: '#eee', padding: 16, borderRadius: 8 }}>
          <div><b>標準出力:</b></div>
          <pre style={{ color: '#8f8' }}>{result.stdout}</pre>
          <div><b>標準エラー:</b></div>
          <pre style={{ color: '#f88' }}>{result.stderr}</pre>
          <div><b>終了コード:</b> {result.exit_code}</div>
          <div><b>実行時間:</b> {result.time} 秒</div>
          {result.debug && (
            <>
              <div style={{marginTop: 16}}><b>デバッグ情報:</b></div>
              <div style={{ color: '#ccc', fontSize: 13 }}>
                <div><b>ホスト側ファイル名:</b> <code>{result.debug.host_file}</code></div>
                <div><b>コンテナ側ファイル名:</b> <code>{result.debug.container_file}</code></div>
                <div><b>コンテナstderr:</b></div>
                <pre>{result.debug.container_stderr}</pre>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default App;
