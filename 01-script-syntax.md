# 一、脚本语法与数据格式

13 条。按「最容易被静默忽略」排序。

---

## 1. 事件 id 必须是「本文件已声明的命名空间.编号」，且恰好一个点

**症状**
```
Error: "Malformed token: W_GER_1, near line: 10" in file: "events/xxx.txt"
Error: "Malformed token: SXLG.W_GER.1, near line: 10"
```

**原因**
HOI4 的事件 id 是 token，格式被硬性要求为 `<命名空间>.<编号>`，**只能有一个点**，且命名空间必须在**同一文件里**用 `add_namespace` 声明过。两条都不满足就报 `Malformed token`，而且报的行号是 `id =` 那一行，看起来完全正常。

**依据**
统计过 TNO 的 32395 个事件 id，**100% 含且仅含一个点**，零例外。

**正确写法**
```paradox
# 文件顶部声明（一个文件可以声明多个）
add_namespace = SXLG_GER
add_namespace = SXLG_USA

country_event = {
	id = SXLG_GER.1          # 一个点
	title = SXLG_GER.1.t     # 本地化键 = id + .t
	...
}
```

**常见错法对照**

| 写法 | 结果 |
|---|---|
| `id = W_GER_1` | ❌ 无点 |
| `id = SXLG.W_GER.1` | ❌ 两个点 |
| `id = SXLG_GER.1`（未声明 `add_namespace = SXLG_GER`） | ❌ 未声明 |
| `add_namespace = SXLG_GER` + `id = SXLG_GER.1` | ✅ |

---

## 2. `ideas` 文件必须有 `ideas = { country = { … } }` 外层

**症状**
```
Error: "Expected idea name followed by its properties between braces: picture, near line: 6"
Error: "Unexpected token: always, near line: 8"
Error: "Unknown category for : XXX It will be ignored"
```
一次刷几百行，而且**每一行都指向看似正常的代码**。

**原因**
`ideas` 的层级是 `ideas` → 分类（`country` / `political` / …）→ 理念。少了「分类」这一层，引擎会把每个理念的第一个属性（`picture`）当成理念名来解析，于是后面全乱。

**错误示范**
```paradox
ideas = {
	A_ARG_idea_x = {
		picture = generic_communist
		...
	}
}
```

**正确写法**
```paradox
ideas = {
	country = {
		A_ARG_idea_x = {
			picture = generic_communist
			allowed = { always = yes }
			modifier = {
				stability_factor = 0.05
			}
		}
	}
}
```

**附带一个陷阱**：往已有文件末尾追加理念时，容易把结尾的 `}` 数量数错。追加后务必跑一次括号计数：

```python
assert s.count('{') == s.count('}')
```

更稳的检查：算每个理念出现位置的**嵌套深度**，深度不对就是层级错了。

```python
for key in ['idea_a', 'idea_b']:
    i = s.find(key)
    print(key, s[:i].count('{') - s[:i].count('}'))   # 应为 2
```

---

## 3. 修饰符（`xxx_factor`）不能当效果直接写

**症状**
```
Error: "Unknown effect-type: research_speed_factor, near line: 1234"
Error: "Unknown effect-type: industrial_capacity_factory, near line: 75"
```

**原因**
`research_speed_factor`、`industrial_capacity_factory`、`consumer_goods_factor`、`army_attack_factor` 这些是**修饰符**（只能出现在 `modifier = { }` 块里），不是**效果**。事件的 `option`、国策的 `completion_reward` 里写它们会被判未知效果。

注意：`stability_factor` 在 TNO 里出现 2000+ 次，但**全部在 `modifier = { }` 块内**。用 grep 找「有没有人这么写」时，必须连带看上下文，否则会得出错误结论。

**合法效果白名单（常用）**
```
add_stability           add_political_power      add_war_support
add_manpower            army_experience          navy_experience
add_research_slot       add_ideas                remove_ideas
add_timed_idea          set_country_flag         clr_country_flag
promote_character       retire_character         kill_country_leader
add_building_construction（必须块形式，见第 10 条）
```

**正确做法：包成限时理念**
```paradox
# 1) 在 ideas 文件里定义一个只含修饰符的理念
ideas = { country = {
	MY_event_mod = {
		picture = generic_communist
		allowed = { always = yes }
		modifier = {
			research_speed_factor = 0.05
		}
	}
} }

# 2) 事件里挂它
option = {
	name = MY.1.a
	hidden_effect = {
		add_timed_idea = { idea = MY_event_mod days = 730 }
	}
}
```

**易错点**：批量生成时理念 id 要带上事件编号（`MOD_<TAG>_<事件号>_<选项字母>`）。只用 `MOD_<TAG>_<选项字母>` 会让同一国家的第 1/2/3 个事件撞同一个 id。

---

## 4. 修饰符名必须在白名单里

**症状**
```
Error: "Unexpected token: industrial_output_factory_max_efficiency_factor"
```

**原因**
「看起来像修饰符」不代表存在。`industrial_output_factory_max_efficiency_factor`、`air_speed_factor`、`maneuver_factor` 这些名字都不存在。

**做法**
从 overhaul 本体里**实际使用过**的修饰符提取白名单，只允许白名单内的名字：

```python
import re, glob, collections
valid = collections.Counter()
for f in glob.glob('<MOD_ROOT>/common/**/*.txt', recursive=True) + glob.glob('<MOD_ROOT>/events/*.txt'):
    t = open(f, encoding='utf-8', errors='replace').read()
    for m in re.finditer(r'modifier = \{([^{}]*)\}', t):
        for line in m.group(1).split('\n'):
            mm = re.match(r'\s*([a-z0-9_]+)\s*=', line)
            if mm:
                valid[mm.group(1)] += 1
print(len(valid))   # TNO 里是 561 个
```

然后对生成器的每个 modifier key 做校验，并准备别名映射：

```python
ALIAS = {
    'industrial_output_factory_max_efficiency_factor': 'production_factory_max_efficiency_factor',
    'air_speed_factor': 'air_attack_factor',
    'division_attack_factor': 'army_attack_factor',
    'army_breakthrough_factor': 'breakthrough_factor',
}
```

**别名映射的副作用**：两个不同的源 key 可能映射到同一个目标 key，导致 `modifier` 里出现重复行（`air_attack_factor` 写两遍）。要在映射后**去重**。

---

## 5. 本地化里的 `\n` 必须是字面反斜杠 n

**症状**
```
Error: "Invalid key name at line 165 and column 1 in localisation/simp_chinese/xxx.yml"
```
同时**那一整条文本在游戏里显示为 key 名或空白**。

**原因**
在 Python 里写 `'第一段\n\n第二段'`（普通字符串）会把 `\n` 变成**真换行**，写进 yml 就变成：

```yml
 SXL.11.d:0 "第一段

第二段"
```
第二行不以空格开头 → 引擎判为非法 key 名，整条失效。

**正确写法**
```python
# 用 raw string
text = r'第一段\n\n第二段'
# 或写两个反斜杠
text = '第一段\\n\\n第二段'
```

**批量修复脚本**（把真换行合并回 `\n`）
```python
import re
KEY = re.compile(r'^ [A-Za-z0-9_.]+:\d+ "')
for l in lines:
    if not l.strip():
        continue
    if l.startswith('l_') or KEY.match(l) or l.startswith(' #'):
        out.append(l)
        continue
    out[-1] = out[-1] + r'\n' + l.strip()   # 续行合并
```

**顺带**：`.yml` 必须是 **UTF-8 with BOM**，否则中文整份不加载。改完跑一次 BOM 检查。

---

## 6. 决议分类必须放在 `common/decisions/categories/` 目录

**症状**
```
Error: "Unknown category: MY_category: {, near line: 1" in file: "common/decisions/MY_decisions.txt"
Error: "Unknown category for : MY_decision_1 It will be ignored"
Error: "Malformed token: {, near line: 5"
Error: "Unexpected token: base, near line: 5"
```
**游戏不崩，但该分类下所有决议全部失效**（一次踩掉过 116 条）。

**原因**
决议分两半：
- **分类定义**（`icon` / `allowed` / `visible` / `priority`）→ 必须放 `common/decisions/categories/*.txt`
- **决议本体** → 放 `common/decisions/*.txt`，用分类名包裹

两半同名，但**位置不能混**。

**正确结构**
```
common/decisions/categories/MY_categories.txt
    MY_category = {
        icon = GFX_decision_category_generic_political_actions
        allowed = { always = yes }
        visible = { date > 1976.1.1 }
        priority = { base = 900 }
    }

common/decisions/MY_decisions.txt
    MY_category = {
        MY_decision_1 = {
            icon = ...
            cost = 50
            ...
        }
    }
```

**注意**：`Unknown category` 之后，引擎会把里面每个决议都报一遍 `Unknown category for`。看到这种「刷屏」时，先找第一行 `Unknown category: X`，问题在 `X` 的定义位置，不在那些决议本身。

---

## 7. 稳定度 / 战争支持度的触发器是 `has_stability` / `has_war_support`

**症状**
```
Invalid trigger 'stability' in events/xxx.txt line : 345
Error: "Unknown trigger-type: stability"
```

**原因**
`stability`、`war_support` 不能当比较对象。要用 `has_stability`、`has_war_support`。

```paradox
# 错
limit = { stability < 0.30 }

# 对
limit = { has_stability < 0.30 }
```

**批量替换时的坑**：正则 `stability [<>]` 会把 `add_stability = 0.05` 也改掉吗？不会——`add_stability` 前面是 `_`，用负向后顾排除即可：

```python
s = re.sub(r'(?<![a-z_])stability ([<>])', r'has_stability \1', s)
```

---

## 8. 国策树的 `country` 块：`factor = 0` 且**不加任何 modifier**，才不会被开局自动选中

**症状**
游戏能正常加载，但你开始玩某个国家时，**它的国策树变成了你新加的那棵**，原 overhaul 的内容全消失。

**原因**
`focus_tree.country` 里的 `factor` / `modifier` 决定「这个树默认分配给谁」。写 `factor = 0` + `modifier = { add = 10 tag = GER }` 会得到 **10 分**，可能高于原树的分数，于是开局就被选中。

**正确写法（只靠事件/决议显式加载时）**
```paradox
focus_tree = {
	id = MY_late_tree
	country = {
		factor = 0        # 不加 modifier，就永远不会被自动分配
	}
	default = no
	...
}
```
然后在决议里显式切：
```paradox
complete_effect = {
	load_focus_tree = { tree = MY_late_tree }
}
```

**设计建议**：一个国家同时只能有一个激活的国策树。子 mod 想给已由 overhaul 分配了树的国家加内容，**不要覆盖原树**（会毁掉原内容），而是：
- 新开一棵「后期树」，用决议/事件在原树走完后切换
- 或者只在原树里插新节点（需要整份复制原树文件，见第 9 条）

---

## 9. 子 mod 永远不要声明 `replace_path`

**症状**
加载后原 overhaul 的内容大面积消失。

**原因**
大型 overhaul 自己已经把 `common/national_focus`、`events`、`common/ideas`、`history/countries` 等 80 多个目录 `replace_path` 掉了。子 mod 再声明一次，等于把 overhaul 的内容也替掉。

**做法**
子 mod **只新增同名目录下的新文件**。同名文件会覆盖（按加载顺序），所以：
- 要改原文件 → 整份复制后改，并承担每次本体更新要 diff 的代价
- 能不改就不改 → 新开树、新加事件、用脚本效果覆盖（见第 10 条）

**例外技巧：整函数覆盖**
HOI4 不支持部分覆盖，但**脚本效果按最后加载的同名定义生效**。所以可以整份复制 overhaul 的某个 `scripted_effect`，加自己的分支，放进子 mod：

```paradox
# 子 mod 里重新定义同名函数，加载顺序在后 → 生效
RUS_load_regional_tree_WRus = {
	if = { limit = { ... 我的条件 ... } load_focus_tree = { tree = MY_regional } }
	if = { limit = { ... 原有条件 ... } load_focus_tree = { tree = ORIGINAL } }
	...
}
```
代价：本体更新时要重新对照（重点看分支有没有增减）。

---

## 10. `add_building_construction` 必须块形式；`victory_points` 是先省后值

**症状**
```
Error: "Unknown effect-type: add_building_construction, near line: N"
```
或州文件里胜利点全部无效。

**正确写法**
```paradox
# 效果里建建筑
random_owned_controlled_state = {
	limit = { free_building_slots = { building = industrial_complex size > 0 } }
	add_building_construction = {
		type = industrial_complex
		level = 2
		instant_build = yes
	}
}
```
```paradox
# 州文件里的胜利点：{ 省份ID 点数 }
history = {
	owner = TAG
	victory_points = { 20008 2 }
}
```
写成 `{ 1 20008 }` 是「省份 1、值 20008」，直接错位。

---

## 11. `units = { }` 不能写在国家历史里，必须放 OOB

**症状**
```
Invalid effect 'units' in history/countries/TAG - Name.txt line : 53
Error: "Unknown effect-type: units"
```
部队不会生成。

**原因**
国家历史文件（`history/countries/*.txt`）只接受「历史指令」；师级单位属于 OOB 数据。

**正确做法**

`history/units/MY_1962.txt`：
```paradox
division_template = {
	name = "步兵师"
	regiments = {
		infantry = { x = 0 y = 0 }
		infantry = { x = 0 y = 1 }
	}
	support = {
		engineer = { x = 0 y = 0 }
	}
}

units = {
	division = {
		name = "第1师"
		location = 20008
		division_template = "步兵师"
	}
	# ... 复制到需要的数量
}
```

`history/countries/TAG - Name.txt`：
```paradox
capital = 20008
oob = "MY_1962"      # 文件名不带扩展名
```

---

## 12. `traits` 里的 token 必须是真实存在的领袖特质

**症状**
加载时报未定义，或领袖没有特质。

**原因**
意识形态名（`communist`）**不一定**是领袖特质。overhaul 里可能刚好有一个同名特质，但多数没有。写之前先确认：

```bash
grep -rn "^\t<traits名> = {" common/country_leader/*.txt
```

不确定就直接去掉 `traits` 块——它是可选的。

---

## 13. `set_popularities` 只能用真实的意识形态**组**名

**症状**
```
Error: "Undefined ideology:democratic"
```
**但同一行里的 `fascism` 却没问题** —— 因为 overhaul 用了 `fascism`，却把「民主」改名成了 `liberalism` / `conservatism` / `progressivism`。

**做法**
先把本体的意识形态组名列出来：

```python
import re, glob
for f in glob.glob('<MOD_ROOT>/common/ideologies/*.txt'):
    s = open(f, encoding='utf-8', errors='replace').read()
    for m in re.finditer(r'^\t([a-z_0-9]+) = \{', s, re.M):
        if 'types' in s[m.end():m.end()+300]:
            print(m.group(1), end='  ')
```

大型 overhaul 的意识形态几乎都是自定义的，**不要用原版的名字**。
