# 五、上线前体检清单 + 二分排查法

---

## A. 每次部署前（30 秒）

```bash
python tools/preflight.py <你的 mod 源码目录>
```

期望输出：

```
1) 脚本文件 N 个，括号问题 0
2) 引用图标 M 个，缺失 0
3) 事件定义 X | 引用 Y | 未定义 0
4) 理念定义 A | 引用 B | 缺失 0
5) 本地化键 C | 需要 D | 缺失 0
6) load_focus_tree 指向不存在的树 0
==============================================
全部通过 ✓
```

**任何一项不为 0，不要部署**。这些错误进游戏后要么闪退，要么静默失效。

---

## B. 部署（逐项，不要删目录）

```bash
DST="%USERPROFILE%/Documents/Paradox Interactive/Hearts of Iron IV/mod/<你的mod>"
SRC="<你的 mod 源码目录>"
for i in common events gfx localisation interface map history descriptor.mod; do
  [ -e "$SRC/$i" ] && cp -rf "$SRC/$i" "$DST/"
done
```

**做完必须检查**：`ls "$DST"` 里**不应出现与 `$DST` 同名的子目录**（那是 `rm -rf` 被拦截造成的嵌套）。

---

## C. 启动（必须清干净）

```powershell
Get-Process hoi4 -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 5
if (Get-Process hoi4 -ErrorAction SilentlyContinue) { '还有残留' } else { '已关闭' }
```

然后启动，**等 4—5 分钟**（大型 overhaul 冷启动）。判断加载完成的标志：

```bash
tail -3 "%USERPROFILE%/Documents/Paradox Interactive/Hearts of Iron IV/logs/game.log"
# 看到 "Executing History from … to <开局日期>" 就是加载完了
```

---

## D. 看日志的三个固定动作

```bash
LOG="%USERPROFILE%/Documents/Paradox Interactive/Hearts of Iron IV/logs"

# 1) 只看自己的命名空间（避免被本体几百行历史错误淹没）
grep -iE "<你的前缀>" "$LOG/error.log" | grep -v "known benign 关键词"

# 2) 看引擎自报的数量
grep -i "Loaded .* provinces" "$LOG/game.log"

# 3) 看有没有崩溃
powershell -NoProfile -Command "Get-WinEvent -FilterHashtable @{LogName='Application'; Id=1000} -MaxEvents 3"
```

**日志时间戳是关键**：如果 `error.log` 的修改时间和你启动的时间对不上，说明**你看的是上一次的日志**（十有八九是新进程没起来，见第 22 条）。

---

## E. 崩溃了怎么二分

**先分三类，别一上来翻代码：**

| 症状 | 大概率原因 | 先查 |
|---|---|---|
| 黑屏 + 0 CPU + 日志只有 3 行 | `dlc_load.json` / `.mod` 的 `path` 指向残缺目录 | 第 23 条 |
| 加载到一半闪退（WER `c0000005`） | 脚本解析后引擎崩，通常是 `ideas` / `focus_tree` 结构错 | 第 2、8 条 + 体检 |
| 能进游戏但功能不对 | 静默失效（分类位置、id 格式、本地化） | 第 1、4、6 条 |

**再二分：按「文件组」整块移走**，不要一个个文件试。

```
先把所有事件文件移走 → 能跑？问题在事件
再把所有国策文件移走 → 能跑？问题在国策
再把所有理念文件移走 → 能跑？问题在理念
```

每组移走前先记录 `ls` 结果，移回来时逐个放回。

**最高效的一条**：**先把最近一次改动整块回滚**。如果回滚后能跑，问题一定在那一次改动里，直接看 diff。

---

## F. 交付前自问

- [ ] `preflight.py` 全绿
- [ ] `error.log` 里自己命名空间的错误为 0（良性警告除外）
- [ ] `game.log` 里引擎自报的数量符合预期（省份数、国家数）
- [ ] **真进游戏**看过一眼：能开局、能点国策、UI 不异常
- [ ] 部署目录没有嵌套
- [ ] 文档里写清「哪些验证过、哪些没验证」

**最后一条最重要**。日志只能证明「加载成功」，证明不了「玩起来对」。把没验证的部分在文档里标出来，比含糊地说「已完成」要诚实得多。
