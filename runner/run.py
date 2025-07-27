

import sys, time, os
if len(sys.argv) < 4:
    print("Usage: run.py <codefile> <stdoutfile> <stderrfile> <timefile>", file=sys.stderr)
    sys.exit(1)
codefile, stdoutfile, stderrfile, timefile = sys.argv[1:5]
with open(codefile, 'r') as f:
    code = f.read()
start = time.time()
try:
    with open(stdoutfile, 'w') as out, open(stderrfile, 'w') as err:
        import sys
        sys.stdout = out
        sys.stderr = err
        try:
            exec(code, {'__name__': '__main__'})
        except Exception as e:
            print(e, file=err)
        out.flush()
        err.flush()
finally:
    end = time.time()
    with open(timefile, 'w') as tf:
        tf.write(str(end-start))
