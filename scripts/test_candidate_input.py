#!/usr/bin/env python3
"""隔离验证纠错候选的原始按键匹配、快速连按和基线候选一致性。

只读取已安装引擎，词库和日志均使用临时目录，不访问账户或云服务。
"""
import argparse
import os
from pathlib import Path
import re
import tempfile
import threading
import time

from test_bionic_daemon import Engine


CASES = ('j' * 12, 'nihao', 'nihoa', 'nhiao', 'zhognguo', 'nhao',
         'OpenClaw', 'BevFusion', 'ABC', 'NIHAO', 'aB', 'Nihao')


def capture(args, harness, base, require_exact):
    work = base / 'dict'
    (work / 'userdict/v5').mkdir(parents=True)
    (work / 'userdict/user_hot_word').mkdir(parents=True)
    path = base / 'engine.log'
    snapshots, timings = [], []
    with path.open('wb') as log:
        engine = Engine(args.engine_dir, work, False, args.qemu, log, harness)
        try:
            engine.command('OPT spans', 'OK')
            for keys in CASES:
                engine.command('C', 'OK')
                parts = list(keys) if keys == CASES[0] else [keys]
                for part in parts:
                    started = time.monotonic()
                    snapshots.append(engine.command('B ' + part, 'CAND'))
                    timings.append(round((time.monotonic() - started) * 1000, 1))
            # 真实节奏发送，不逐键等候选；每条命令仍须恰好得到一个回复。
            engine.command('C', 'OK')
            errors = []

            def type_repeated():
                try:
                    for _ in range(24):
                        engine.process.stdin.write(b'B j\n')
                        time.sleep(.03)
                except Exception as error:
                    errors.append(error)

            writer = threading.Thread(target=type_repeated)
            writer.start()
            try:
                replies = [engine.line(15) for _ in range(24)]
            finally:
                writer.join(timeout=5)
            assert not writer.is_alive() and not errors, '快速输入发送失败'
            assert all(line == 'SKIP' or line.startswith('CAND\t') for line in replies), '候选协议错位'
            assert replies[-1].startswith('CAND\t'), '最后一批输入没有候选'
            engine.command('C', 'OK')
            # 用下一次普通输入检查积压请求是否已处理完，不能把旧回复当成新候选。
            snapshots.append(engine.command('B nihao', 'CAND'))
        finally:
            engine.close()
    waits = re.findall(r'wait_cand took (\d+) ms exact=(\d)', path.read_text())
    assert waits, '缺少候选匹配记录'
    if require_exact:
        assert all(exact == '1' for _, exact in waits), '纠错原始按键未完整还原，仍在静默等待'
    return snapshots, timings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine-dir', type=Path, required=True)
    parser.add_argument('--harness', type=Path, required=True)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--qemu')
    args = parser.parse_args()
    args.engine_dir = args.engine_dir.resolve()
    # 测试始终关闭云端并使用默认静默保护，不能靠调低等待窗口通过。
    for key in list(os.environ):
        if key.startswith('WETYPE_') or key in ('LD_PRELOAD', 'QEMU_SET_ENV'):
            os.environ.pop(key, None)
    with tempfile.TemporaryDirectory(prefix='wetype-candidate-input.') as directory:
        base = Path(directory)
        fixed, timings = capture(args, args.harness.resolve(), base / 'fixed', True)
        print('修复后各请求耗时(ms)：', timings, flush=True)
        if args.baseline:
            old, old_times = capture(args, args.baseline.resolve(), base / 'baseline', False)
            assert fixed == old, '修复前后的完整候选不一致'
            print('基线各请求耗时(ms)：', old_times, flush=True)
            print('完整候选与基线一致', flush=True)
    print('CANDIDATE_INPUT_RESULT = PASS', flush=True)


if __name__ == '__main__':
    main()
