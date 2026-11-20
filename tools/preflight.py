#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""HOI4 子 mod 上线前静态体检（不开游戏）。

把脚本层面能查出来的硬错误先扫掉：括号失衡、图标缺失、事件 id 未定义、
理念缺失、本地化缺键、load_focus_tree 指向不存在的树。

用法:
    python preflight.py <你的mod目录> [母mod目录] [游戏本体目录]

    # 例
    python preflight.py "D:/mods/si_xiaolin" "D:/steam/workshop/content/394360/2438003901"

母 mod 目录可选。给了就会把母 mod 里已存在的 sprite / 事件 id 也算作"已定义"，
否则你引用 TNO 自带的图标会被误报为缺失。
"""
import os
import re
import sys
import glob
import collections

P = collections.defaultdict(list)

if len(sys.argv) < 2:
    print(__doc__)
    sys.exit(1)

MOD = os.path.abspath(sys.argv[1])
PARENT = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else None
GAME = os.path.abspath(sys.argv[3]) if len(sys.argv) > 3 else None

if not os.path.isdir(MOD):
    print('mod 目录不存在: %s' % MOD)
    sys.exit(1)


def rd(p):
    return open(p, encoding='utf-8', errors='replace').read()


def scan(root, pattern):
    if not root or not os.path.isdir(root):
        return []
    return glob.glob(os.path.join(root, '**', pattern), recursive=True)


print('mod      = %s' % MOD)
print('parent   = %s' % (PARENT or '(未提供，母 mod 资源不参与去重)'))
print('game     = %s' % (GAME or '(未提供，本体 sprite 不参与去重)'))
print('-' * 52)

# ---------- 1. 括号 ----------
txts = scan(MOD, '*.txt')
for f in txts:
    s = rd(f)
    d = s.count('{') - s.count('}')
    if d != 0:
        P['braces'].append('%s %+d' % (os.path.relpath(f, MOD), d))
print('1) 脚本文件 %d 个，括号问题 %d' % (len(txts), len(P['braces'])))

# ---------- 2. sprite ----------
sprites = set()
for root in (GAME, PARENT, MOD):
    for f in scan(root, '*.gfx'):
        sprites |= set(re.findall(r'name\s*=\s*"(GFX_[A-Za-z0-9_]+)"', rd(f)))
used = set()
for f in txts:
    s = rd(f)
    used |= set(re.findall(r'icon = (GFX_[A-Za-z0-9_]+)', s))
    used |= set(re.findall(r'picture = (GFX_[A-Za-z0-9_]+)', s))
missing = sorted(used - sprites)
print('2) 引用图标 %d 个，缺失 %d' % (len(used), len(missing)))

# ---------- 3. 事件 id ----------
ev_files = scan(MOD, 'events/*.txt') + scan(MOD, 'events/**/*.txt')
defined, called = set(), set()
for f in set(ev_files):
    s = rd(f)
    defined |= set(re.findall(r'^\s*id = ([A-Za-z0-9_.]+)', s, re.M))
    called |= set(re.findall(r'id = ([A-Za-z0-9_.]+\.[0-9]+)', s))
for f in scan(PARENT, 'events/*.txt'):
    defined |= set(re.findall(r'^\s*id = ([A-Za-z0-9_.]+)', rd(f), re.M))
undefined = sorted(called - defined)
print('3) 事件定义 %d | 引用 %d | 未定义 %d' % (len(defined), len(called), len(undefined)))

# ---------- 4. idea ----------
ideas = set()
for f in scan(MOD, 'common/ideas/*.txt'):
    ideas |= set(re.findall(r'^\t{1,4}([A-Za-z0-9_]+) = \{', rd(f), re.M))
need = set()
for f in txts:
    s = rd(f)
    need |= set(re.findall(r'add_ideas = ([A-Za-z0-9_]+)', s))
    need |= set(re.findall(r'add_timed_idea = \{\s*idea = ([A-Za-z0-9_]+)', s))
    need |= set(re.findall(r'has_idea = ([A-Za-z0-9_]+)', s))
idea_missing = sorted(need - ideas)
print('4) 理念定义 %d | 引用 %d | 缺失 %d' % (len(ideas), len(need), len(idea_missing)))

# ---------- 5. 本地化 ----------
# 先收集所有国策树 id，后面要拿来把它们从"需要本地化的 key"里剔掉
trees = set()
for g in scan(MOD, 'common/national_focus/*.txt'):
    trees |= set(re.findall(r'focus_tree = \{\s*\n\s*id = ([A-Za-z0-9_]+)', rd(g), re.M))
for f in scan(PARENT, 'common/national_focus/*.txt'):
    trees |= set(re.findall(r'focus_tree = \{\s*\n\s*id = ([A-Za-z0-9_]+)', rd(f), re.M))

keys = set()
for f in scan(MOD, 'localisation/**/*.yml'):
    raw = open(f, 'rb').read()
    if not raw.startswith(b'\xef\xbb\xbf'):
        P['no_bom'].append(os.path.relpath(f, MOD))
    keys |= set(re.findall(r'^\s*([A-Za-z0-9_.\-]+):\d*\s*"',
                           raw.decode('utf-8-sig', 'replace'), re.M))
want = set()
for f in scan(MOD, 'common/national_focus/*.txt'):
    want |= set(re.findall(r'^\s*id = ([A-Za-z0-9_]+)', rd(f), re.M))
want -= trees  # 树 id 本身不需要本地化
for f in set(ev_files):
    s = rd(f)
    want |= set(re.findall(r'title = ([A-Za-z0-9_.]+)', s))
    want |= set(re.findall(r'desc = ([A-Za-z0-9_.]+)', s))
    want |= set(re.findall(r'name = ([A-Za-z0-9_.]+)', s))
loc_missing = sorted(x for x in want - keys if x and not x.startswith('$'))
print('5) 本地化键 %d | 需要 %d | 缺失 %d' % (len(keys), len(want), len(loc_missing)))

# ---------- 6. load_focus_tree 指向 ----------
tree_missing = []
for f in scan(MOD, 'common/decisions/**/*.txt') + scan(MOD, 'common/decisions/*.txt'):
    s = rd(f)
    for tree in re.findall(r'load_focus_tree = \{\s*tree = ([A-Za-z0-9_]+)', s):
        if tree not in trees:
            tree_missing.append('%s -> %s' % (os.path.basename(f), tree))
print('6) 国策树 %d 棵，load_focus_tree 指向不存在 %d' % (len(trees), len(tree_missing)))

# ---------- 汇总 ----------
print('\n' + '=' * 52)
bad = False
for name, items in (
    ('braces', P['braces']),
    ('missing_sprite', missing),
    ('event_undefined', undefined),
    ('idea_missing', idea_missing),
    ('loc_missing', loc_missing),
    ('no_bom', P['no_bom']),
    ('tree_missing', tree_missing),
):
    if items:
        bad = True
        print('!! %-18s %d' % (name, len(items)))
        for x in items[:8]:
            print('      %s' % x)
if not bad:
    print('全部通过')
sys.exit(1 if bad else 0)
