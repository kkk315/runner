const fs = require('fs');
const { performance } = require('perf_hooks');


let code = '';
let stdinData = '';
if (process.argv.length > 3) {
  code = fs.readFileSync(process.argv[2], 'utf-8');
  stdinData = fs.readFileSync(process.argv[5], 'utf-8');
  runCode(code, stdinData);
} else {
  process.stdin.on('data', chunk => code += chunk);
  process.stdin.on('end', () => runCode(code, ''));
}

function runCode(code, stdinData) {
  // monkey patch process.stdin
  const { Readable } = require('stream');
  process.stdin = Readable.from([stdinData]);
  const start = performance.now();
  try {
    eval(code);
  } catch (e) {
    console.error(e);
  }
  const end = performance.now();
  console.error(`\n[EXECUTION_TIME] ${(end-start)/1000}`);
}
