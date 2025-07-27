const fs = require('fs');
const { performance } = require('perf_hooks');

let code = '';
if (process.argv.length > 2) {
  code = fs.readFileSync(process.argv[2], 'utf-8');
  runCode(code);
} else {
  process.stdin.on('data', chunk => code += chunk);
  process.stdin.on('end', () => runCode(code));
}

function runCode(code) {
  const start = performance.now();
  try {
    eval(code);
  } catch (e) {
    console.error(e);
  }
  const end = performance.now();
  console.error(`\n[EXECUTION_TIME] ${(end-start)/1000}`);
}
