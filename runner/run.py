import sys, time, os, json
if len(sys.argv) < 2:
    print("Usage: run.py <tmpdir>", file=sys.stderr)
    sys.exit(1)
tmpdir = sys.argv[1]
codefile = os.path.join(tmpdir, 'code.py')
if not os.path.exists(codefile):
    print("No code.py found in tmpdir", file=sys.stderr)
    sys.exit(2)
stdinfile = os.path.join(tmpdir, 'stdin.txt')
stdoutfile = os.path.join(tmpdir, 'stdout.txt')
stderrfile = os.path.join(tmpdir, 'stderr.txt')
timefile = os.path.join(tmpdir, 'time.txt')
exit_code_file = os.path.join(tmpdir, 'exit_code.txt')

start = time.time()
exit_code = 1
try:
    cmd = f'{sys.executable} {codefile} < {stdinfile} > {stdoutfile} 2> {stderrfile}'
    exit_code = os.system(cmd)
finally:
    end = time.time()
    with open(timefile, 'w') as tf:
        tf.write(str(end-start))
    try:
        with open(exit_code_file, 'w') as ef:
            ef.write(str(exit_code))
    except Exception:
        pass

