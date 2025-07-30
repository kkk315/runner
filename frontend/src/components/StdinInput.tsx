import React from 'react';

type StdinInputProps = {
  stdin: string;
  onStdinChange: (stdin: string) => void;
};

const StdinInput: React.FC<StdinInputProps> = ({ stdin, onStdinChange }) => (
  <div style={{ marginTop: 16 }}>
    <label style={{ fontWeight: 'bold' }}>標準入力:</label>
    <textarea
      rows={4}
      style={{ width: '100%', fontFamily: 'monospace', fontSize: 15, marginTop: 4, borderRadius: 4, border: '1px solid #888', padding: 6, background: '#222', color: '#fff' }}
      value={stdin}
      onChange={e => onStdinChange(e.target.value)}
      placeholder="ここに標準入力を記述"
    />
  </div>
);

export default StdinInput;
