# 四、内容设计与规模化

5 条。这一节不谈语法，谈「怎么让几百个国家的剧情不显得是同一套模板」。

---

## 27. 子 mod 能改什么、不能改什么

在一个成熟 overhaul 上做子 mod，能力边界是这样的：

| 想做的事 | 可行做法 | 代价 |
|---|---|---|
| 加国家事件 | 新文件，`id` 用自有命名空间 | 无 |
| 加国策树 | 新开树 + 决议/事件显式 `load_focus_tree` | 一个国家同时只能有一棵树，会替掉原树 |
| 改原国策树 | 整份复制原文件后改 | 本体每次更新要重新 diff |
| 改阶段分发逻辑 | 整函数复制 `scripted_effects` 并加分支 | 同上 |
| 加人物 | 新 `common/characters/*.txt` | 无 |
| 加省份/陆地 | 自带整份地图位图 | 约 63 MB + 本体更新要重刷 |
| 加超事件 | 往 `hidden_ideas` 加 token + 三处文本 + 一张图 | 见第 28 条 |
| 改 `defines` | 新增一个 `common/defines/ZZZ_xxx.lua`，**文件名排在本体之后** | 只影响被覆盖的那几个 key |

**文件加载顺序的经验法则**：同名文件后加载的覆盖先加载的；不同名文件合并。所以
- 想覆盖 → 同名文件，且文件名排序靠后（如 `ZZZ_`）
- 想追加 → 新文件名

---

## 28. 超事件（superevent）不是原版机制，是 overhaul 自研的

**不要去找 `superevent = yes` 这种字段，没有。**

TNO 的实现链路是：

```
1. token 声明    common/ideas/xxx.txt → ideas = { hidden_ideas = { SE_XXX = {} } }
2. 触发          set_temp_variable = { TNO_temp_super_event = token:SE_XXX }
                 TNO_fire_super_event = yes
3. 文本解析      common/scripted_localisation/… 里 defined_text 把 token 拆成三个 key：
                   SE_XXX      标题
                   SE_XXX_D    正文
                   SE_XXX_A    按钮
4. 图片          interface/*.gfx 里注册 spriteType，name = "GFX_SE_XXX"
                 → 默认解析规则是 "GFX_" + token 名
5. 显示范围      必须在 every_country = { limit = { is_ai = no } } 里触发，
                 逐个真人玩家推。只在本国作用域触发的话，非该国玩家看不到
```

**正确调用写法**
```paradox
hidden_effect = {
	every_country = {
		limit = { is_ai = no }
		set_temp_variable = { TNO_temp_super_event = token:SE_MY_EVENT }
		TNO_fire_super_event = yes
	}
}
```

**两个坑**
- 用 `set_variable` 而不是 `set_temp_variable` 可能不生效（原版用的是 temp）
- 三个文本键缺一个就会显示空白或 key 名

**已知警告**
```
Token SE_MY_EVENT is a dynamic token, this can cause OOS depending on how it's used,
please add it as a synchronized dynamic token to prevent OOS:es
```
这是**多人同步**提示，单人游戏无害。要彻底消除需要把 token 改成 synchronized 形式（未深入研究）。

---

## 29. 用事件「干掉」原领袖，而不是软接管

**需求**：「新人物上台，取代原有领袖」。

**错误做法**
`promote_character = 新人物` —— 这只是把新人物提为领袖，原领袖还活着、还在人物列表里，叙事上等于「和平交接」。对一个政变/革命题材来说很假。

**正确做法**

```paradox
# 方案一：直接处死（overhaul 自己也在用的效果）
kill_country_leader = yes

# 方案二：逼退（对具体人物用 retire）
if = {
	limit = { has_country_flag = original_leader_A_in_power }
	retire_character = ORIGINAL_A
}
else_if = {
	limit = { has_country_flag = original_leader_B_in_power }
	retire_character = ORIGINAL_B
}
promote_character = NEW_LEADER
```

**要点**
- 先判断当前是谁在台上（用 overhaul 的状态 flag），再决定移除谁
- `kill_country_leader` 杀的是「当前领袖」，不需要知道 id
- 给玩家一个**拒绝选项**（什么都不做），否则这条线变成强制剧情

**叙事设计**：如果原领袖是通过选举/任命上台的，用 `retire`（逼退）更合理；如果是军事强人，用 `kill` 更符合政治逻辑。两种走法给不同的稳定度/战争支持度代价。

---

## 30. 多结局：条件要落在「玩家做过的选择」上，不是随机

**做法**
用 flag/理念做分支，判序固定（先判失败，再判路线，最后落到中道）：

```paradox
if = {
	limit = { OR = { has_stability < 0.30  has_country_flag = lost_key_ally } }
	country_event = { id = ENDING.failure }
}
else_if = {
	limit = { OR = { AND = { has_idea = A  has_idea = B }  has_country_flag = slow_line_done } }
	country_event = { id = ENDING.alienation }
}
else_if = {
	limit = { AND = { has_country_flag = coup  has_war_support > 0.55 } }
	country_event = { id = ENDING.military }
}
else_if = {
	limit = { AND = { has_idea = C  has_idea = D } }
	country_event = { id = ENDING.republic }
}
else = {
	country_event = { id = ENDING.default }
}
```

**三个经验**
- **失败线不要写成「被外敌打败」**。对一个小国而言，更真实的失败是「中央开会没人来」——各省书记各管一块，旗子还在，国家已经散了。这比军事失败更难写，但可信得多。
- **每条路的代价要写在效果里**。比如「革命成功」的战争支持度是**下降**的：一个打赢了所有战争的国家，终于开始不想打仗了。这才是成功。
- **替代路径要能互相抵达同一结局**。比如「接受缓行」+「一党宪章」也能进异化结局，不一定要「查封报纸 + 一党宪章」两条同时满足。这样玩家的选择才有实际重量。

---

## 31. 模板化内容：怎么不让 119 个国家看起来一模一样

**问题**
给上百个国家批量生成国策，最省事的写法是「10 个槽位 × 3 套模板 + md5 选一个」。结果：

- **40 个国家拿到同一条标题**（因为该变体不含国名，md5 全部撞到同一个）
- **语法错**：模板 `第{n}个五年` 把国名当序数词填进去，生成「第阿塞拜疆个五年」

**三条修正**

1. **每个变体至少在标题里含 `{n}`**；不含的在生成时自动加国名前缀：
   ```python
   if name not in zh_t:
       zh_t = '%s · %s' % (name, zh_t)
   ```

2. **选择器用「按槽位轮转」而不是纯 md5**，保证相邻国家不撞：
   ```python
   _ROT = {}
   def pick(lst, tag, slot):
       i = _ROT.get(slot, 0); _ROT[slot] = i + 1
       h = int(hashlib.md5((tag + slot).encode()).hexdigest(), 16)
       return lst[(i + h) % len(lst)]
   ```

3. **变体池要够大**。3 套 → 6 套后，119 个根节点标题从「最多重复 40 次」变成**全部不同**。

**验证方法**
```python
import re, collections
loc = open('localisation/simp_chinese/xxx.yml', encoding='utf-8-sig').read()
pairs = re.findall(r'^ ([A-Z]{3})_bulk_root:0 "([^"]+)"', loc, re.M)
t = collections.Counter(v for _, v in pairs)
print(len(pairs), len(t), t.most_common(1))
# 期望：119 119 [('某标题', 1)]
```

**诚实的说法**
模板化内容做到最后仍然是「结构性完整，内容不专属」。想真正做到每国不同，只能逐国写——那是另一个量级的工作。**在文档里把这件事写清楚，比假装它不存在要好。**

---

## 附加：关于「体量」

mod 的体积基本只由**美术资源**决定，文本贡献极小：

| 内容 | 体积参考 |
|---|---|
| 1300 条国策 + 500 事件 + 5700 条本地化 | 约 2 MB |
| 19 张领袖肖像（PNG，312×420） | 约 2 MB |
| 20 张事件图（PNG，1024×576，灰度） | 约 4 MB |
| 2 张超事件图 | 约 0.7 MB |
| **3 个地图位图（5120×2560）** | **约 63 MB** |

所以「把 mod 做到 100 MB」这件事，靠堆文本是做不到的，靠地图/超事件/加载界面这些图片才行。
