#!/usr/bin/env python3
"""在私有 D-Bus 会话验证 Ctrl+B 前缀直通，不触碰桌面输入法。"""
from dbus_test_client import Client, paused_engine, pump

CTRL_L, SHIFT_L = 0xFFE3, 0xFFE1


def fresh():
    client = Client('wetype-prefix-key')
    client.focus()
    return client


def prefix(client):
    assert not client.press('b', states=4), 'Ctrl+B 必须交给应用'
    assert not client.press('b', states=4, release=True)
    assert not client.press(CTRL_L, release=True), '松开 Ctrl 不应消耗前缀'


def ordinary_input(client):
    assert client.press('n'), '前缀之后必须恢复中文输入'
    client.press('esc')


client = fresh()
prefix(client)
for release in (False, False, True):
    assert not client.press('x', release=release), '后续按键及长按、释放必须直通'
assert not client.commits, '直通不能用 CommitString 模拟输入 x'
ordinary_input(client)
print('PASS Ctrl+B 松开后 x、长按及释放直通，随后恢复中文', flush=True)

client = fresh()
prefix(client)
assert not client.press(','), '前缀后的逗号不能转换成中文标点'
client.press(',', release=True)
assert not client.commits
client.press(',')
assert client.commits == ['，'], client.commits
print('PASS 前缀后的标点直通且仅作用于一个按键', flush=True)

client = fresh()
prefix(client)
client.press(SHIFT_L, states=1)
assert not client.press('X', states=1), 'Shift 组合键也应交给应用'
client.press('X', states=1, release=True)
client.press(SHIFT_L, release=True)
ordinary_input(client)
print('PASS Shift 组合键直通且不意外切换中英', flush=True)

client = fresh()
prefix(client)
client.press(SHIFT_L, states=1)
assert not client.press('X', states=1)
client.press(SHIFT_L, release=True)
assert not client.press('x', release=True), '先松开 Shift 时也应识别字母释放'
assert client.press('X', states=1), '释放后的大写字母必须恢复中文模式的英文混输'
client.press('esc')
print('PASS 先松开 Shift 不残留透传状态', flush=True)

client = fresh()
prefix(client)
client.press(SHIFT_L)
client.press(SHIFT_L, release=True)
assert not client.press('x'), '单独松开 Shift 也不应消耗前缀或切换中英'
client.press('x', release=True)
ordinary_input(client)
print('PASS 前缀期间轻按 Shift 不切换中英', flush=True)

client = fresh()
assert not client.press('c', states=4)
client.press('c', states=4, release=True)
ordinary_input(client)
assert not client.press('b', states=12), 'Ctrl+Alt+B 本身直通'
ordinary_input(client)
print('PASS 其他 Ctrl 快捷键不启用前缀直通', flush=True)

client = fresh()
prefix(client)
client.ic.FocusOut()
other = fresh()
ordinary_input(other)
other.ic.FocusOut()
client.focus()
ordinary_input(client)
print('PASS 失焦清理前缀且不影响其他输入框', flush=True)

client = fresh()
prefix(client)
client.ic.Reset()
ordinary_input(client)
client.press(SHIFT_L)
client.press(SHIFT_L, release=True)
assert not client.press('n'), '普通轻按 Shift 仍应切到英文'
client.press(SHIFT_L)
client.press(SHIFT_L, release=True)
ordinary_input(client)
print('PASS 重置清理前缀且普通 Shift 中英切换正常', flush=True)

client = fresh()
client.type('nihao')
prefix(client)
assert not client.press('x')
client.press('x', release=True)
assert not client.commits
client.press('space')
assert client.commits == ['你好'], client.commits
print('PASS 已有拼音不混入前缀命令字符', flush=True)

client = fresh()
client.type('nihao')
client.press('esc')
client.commits.clear()
with paused_engine():
    client.type('nihao', wait=False)
    client.press('space', delay=0)
    prefix(client)
    assert not client.press('x'), '待选词状态的 Ctrl+B 也应保护后续按键'
    client.press('x', release=True)
    assert client.commits == ['nihao '], client.commits
pump(.5)
ordinary_input(client)
print('PASS 待选词时先保留已输入文字，再直通前缀命令', flush=True)
