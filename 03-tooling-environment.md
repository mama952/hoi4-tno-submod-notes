# 三、工具链、部署与环境

6 条。这一节的共同点是：**问题不在代码里，但会让你误判代码有问题**。

---

## 21. `rm -rf` 可能被安全软件静默拦截，导致 `cp` 拷进旧目录形成嵌套

**症状**
改了文件、部署了、重启游戏，但改动**完全没有生效**。日志和之前一模一样。

**原因**
某些环境（含部分 Windows 安全策略、沙箱）会拦截批量删除。`rm -rf <dir>` 返回成功但实际没删。紧接着的

```bash
rm -rf "$DST" && cp -r "$SRC/" "$DST/"
```

就变成了「把源码拷进一个仍然存在的目录」，产生：

```
$DST/mysubmod/mysubmod/     ← 新内容在这里
$DST/mysubmod/...           ← 游戏读的是这里（旧内容）
```

**排查方法**
```bash
ls -la "$DST" | head
# 如果看到与目标同名的子目录，就是嵌套了

# 对比时间戳
ls -la --time-style=+%H:%M:%S "$DST/events/xxx.txt" "$SRC/events/xxx.txt"
```

**正确做法：逐项覆盖，不做整目录删除**
```bash
DST="<MOD_DEPLOY_DIR>"
SRC="<MOD_SOURCE_DIR>"
for i in common events gfx localisation interface map history descriptor.mod; do
  [ -e "$SRC/$i" ] && cp -rf "$SRC/$i" "$DST/"
done
```

**部署清单容易漏的两项**：`map` 和 `history`。只拷 `common/events/gfx/localisation/interface` 是很多模板的默认写法，做地图或国家改动时会漏掉最关键的两块。

---

## 22. HOI4 有单实例锁：旧进程在跑时新进程直接退出，日志不刷新

**症状**
改完文件重启游戏，查 `error.log` 发现**时间戳还是上一次的**，内容也没变。以为改动没生效，反复改代码。

**原因**
`hoi4.exe` 有互斥锁。已有实例在运行时，新进程启动后**静默退出**，不会写日志，也不会弹窗。

**排查方法（务必看进程启动时间，不要只看「进程存在」）**
```powershell
Get-Process hoi4 | Select-Object Id, StartTime, @{n='GB';e={[math]::Round($_.WorkingSet64/1GB,2)}}
```
如果 `StartTime` 比你刚才启动的时间早，说明**当前进程是旧的**，你的新进程根本没跑起来。

**正确流程**
```powershell
# 1) 彻底关闭
Get-Process hoi4 -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 5
# 2) 确认已清空
if (Get-Process hoi4 -ErrorAction SilentlyContinue) { '还有残留' } else { '已关闭' }
# 3) 再启动
```
关掉后**等 3—5 秒**再启动，否则文件句柄还没释放。

**加载耗时参考**：大型 overhaul（5 GB 资源 + 20000 省份）冷启动到主菜单约 **4—5 分钟**。前 30 秒只写 3 行 `defines loaded`，别以为卡死了。

---

## 23. `dlc_load.json` 被写坏 → 黑屏、0 CPU、日志只有 3 行

**症状**
```
error.log 只有 3 行（Invalid supported_version …）
game.log  只有 "4489 defines loaded"
进程存在、内存 200–300 MB、CPU 占用 0、窗口响应=False
Windows 事件日志：Exception code 0xc0000005（访问违例）
```

**原因**
`%USERPROFILE%\Documents\Paradox Interactive\Hearts of Iron IV\dlc_load.json` 的 `enabled_mods` 里指向了一个**残缺的 mod 目录**（比如一个只剩一半文件的旧备份）。引擎加载到一半崩溃。

这类错误**不会在 error.log 里留下任何有用信息**，因为崩在脚本解析之前。

**排查顺序**
1. 看 `dlc_load.json` 的 `enabled_mods`，逐个检查对应 `.mod` 文件里的 `path=` 是否指向**存在的、完整的**目录
2. `path` 里带 `_bak` / `obsolete` / `backup` 字样的一律可疑
3. 客户端启动器有时会自动重写这个文件，要连启动器的「播放集」配置一起改

**验证「是 mod 的问题还是环境的问题」的最快方法**
把 `enabled_mods` 清空（只留 overhaul 本体），启动：
- 能进主菜单 → 是你新加的 mod
- 还是黑屏 → 是环境/本体文件的问题

---

## 24. 静态体检：不开游戏就能查掉一大半错误

写一个 `preflight.py`，每次部署前跑。它能抓到：

| 检查项 | 抓什么 |
|---|---|
| 括号平衡 | 每个 `.txt` 的 `{` `}` 数量 |
| 图标引用 | `icon = GFX_x` / `picture = GFX_x` 是否在 `.gfx` 里定义过 |
| 事件 id | 被 `country_event = { id = X }` 引用的 X 是否定义过 |
| 理念引用 | `add_ideas` / `has_idea` 引用的 id 是否存在 |
| 本地化 | 所有国策 id、事件 title/desc、选项名是否都有对应 key；BOM 是否存在 |
| 切树 | `load_focus_tree = { tree = X }` 的 X 是否存在 |

**它抓不到的**（必须进游戏）：
- 效果类型是否合法（`Unknown effect-type`）
- 触发器名是否正确（`Unknown trigger-type`）
- 事件的**实际触发**与分支走向
- 地图渲染、UI 显示

所以体检通过 ≠ 能跑，但能省掉 70% 的往返。

见 [tools/preflight.py](tools/preflight.py)。

---

## 25. 用 CWTools 做语法检查，但别全信它

**装法**
```bash
code --install-extension tboby.cwtools-vscode
```

**它能做的**：Paradox 语法高亮、括号结构校验、`GFX_` / 本地化 key / 脚本效果的**交叉引用**检查。这是唯一能在保存时就发现「引用了不存在的 sprite」的工具。

**它抓不到的**：
- 语义层的问题（比如国策树 `country` 块会不会抢树）
- 决议分类放错目录（它能看出结构，但不知道引擎的分目录规则）
- 地图文件的一切

**建议**：CWTools 当编辑器辅助，`preflight.py` 当提交前门禁，游戏日志当最终判据。三层都要。

---

## 26. 生成器思维：数据表 + 脚本，不要手写几百条

**背景**
内容量到几百上千条时（1300 条国策、500 条事件），手写的成本不是「打字」，是**改不动**：改一个字段要动几百个地方，每次都引入新的转义错误。

**做法**
```
content/
  arc_west.json      ← 数据（国家、事件、选项、效果、中英文本）
  arc_asia.json
  late_trees.json
tools/
  gen_arc.py         ← 读 JSON → 输出 events/*.txt + ideas/*.txt + localisation/*.yml
preflight.py         ← 校验生成结果
```

**收益**
- 改内容只改 JSON，不动脚本
- 校验逻辑只写一次（修饰符白名单、id 唯一性、括号平衡）
- 中英文永远同步（同一份数据出两份 yml）

**代价**
- 生成器本身要处理转义（见第 5 条）
- 生成的文件要标记「自动生成，勿手改」，否则下次重新生成会覆盖手改内容

**Python 字符串转义的硬规则**：所有要写进 `.yml` / `.txt` 的文本，**一律用 raw string**（`r"..."`）。否则 `\n`、`\t`、`\"` 会在你不知情的地方变成真字符。
