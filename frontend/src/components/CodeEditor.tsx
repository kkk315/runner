import React from 'react';
import MonacoEditor from '@monaco-editor/react';

type CodeEditorProps = {
  language: string;
  code: string;
  onLanguageChange: (lang: string) => void;
  onCodeChange: (code: string) => void;
};

const languageMap: Record<string, string> = {
  python: 'python',
  node: 'javascript',
};

function CodeEditor({ language, code, onLanguageChange, onCodeChange }: CodeEditorProps) {
  return (
    <div>
      <label>
        言語:
        <select value={language} onChange={e => onLanguageChange(e.target.value)} style={{ marginLeft: 8 }}>
          <option value="python">Python</option>
          <option value="node">Node.js</option>
        </select>
      </label>
      <div style={{ marginTop: 8 }}>
        <MonacoEditor
          height="300px"
          defaultLanguage={languageMap[language] || 'python'}
          language={languageMap[language] || 'python'}
          value={code}
          theme="vs-dark"
          options={{
            fontSize: 16,
            fontFamily: 'monospace',
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            wordWrap: 'on',
            automaticLayout: true,
          }}
          onChange={v => onCodeChange(v ?? '')}
        />
      </div>
    </div>
  );
}

export default CodeEditor;
