import sys, time, os, json
import resource

# --- リソース制限の設定 ---
# メモリ制限（CONTAINER_MAX_MEM: 例 '512m'）
mem_env = os.environ.get('CONTAINER_MAX_MEM', '512m')
def parse_mem_limit(val):
    val = val.lower()
    if val.endswith('g'):
        return int(float(val[:-1]) * 1024 * 1024 * 1024)
    if val.endswith('m'):
        return int(float(val[:-1]) * 1024 * 1024)
    if val.endswith('k'):
        return int(float(val[:-1]) * 1024)
    return int(val)
mem_limit = parse_mem_limit(mem_env)
resource.setrlimit(resource.RLIMIT_AS, (mem_limit, mem_limit))

# CPU時間制限（CONTAINER_MAX_CPU: 秒数で指定、例 '2'）
cpu_env = os.environ.get('CONTAINER_MAX_CPU', '1')
try:
    cpu_limit = int(float(cpu_env))
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit))
except Exception:
    pass

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

