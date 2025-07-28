import React from 'react';

interface ResultPanelProps {
  result: {
    stdout?: string;
    stderr?: string;
    exit_code?: number;
    time?: number;
    debug?: any;
  } | null;
}

const ResultPanel: React.FC<ResultPanelProps> = ({ result }) => {
  if (!result) return null;
  return (
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
            <div><b>ホスト側コードファイル:</b> <code>{result.debug.host_code_file}</code></div>
            <div><b>コンテナ側コードファイル:</b> <code>{result.debug.container_code_file}</code></div>
            <div><b>ホスト側標準入力ファイル:</b> <code>{result.debug.host_stdin_file}</code></div>
            <div><b>コンテナ側標準入力ファイル:</b> <code>{result.debug.container_stdin_file}</code></div>
            <div><b>標準入力プレビュー:</b></div>
            <pre>{result.debug.stdin_preview}</pre>
            <div><b>コンテナstderr:</b></div>
            <pre>{result.debug.container_stderr}</pre>
          </div>
        </>
      )}
    </div>
  );
};

export default ResultPanel;
