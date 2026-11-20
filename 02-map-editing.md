# 二、地图级改动：真新增省份与陆地

7 条。这一节是整份文档里最「不可逆」的部分——改错了会把地图搞坏，而且排查成本最高。

**前置结论**：在成熟 overhaul 上，「借一块空地建国」基本不成立。实测某 overhaul 的 16347 个陆地省份**全部**已被州占用，无 owner 的州 0 个，未分配的省份 3495 个但**全部是海**。

所以「新增国家」只有三条路：

| 方案 | 做法 | 冲突风险 |
|---|---|---|
| A 复用空省 | 找未被任何州占用的陆地省份 | 实地扫描后通常**不存在** |
| B 海改陆 | 把选中的海省份改成陆地 | 低。只改 type 与地形色 |
| C 真新增省份 | 画新色块进 provinces.bmp + 追加 definition.csv | 中。要自带整份地图位图 |

下面的内容针对 **C（真新增）**，B 是它的简化版。

---

## 14. `definition.csv` 的 RGB 三列就是位图里的实际颜色——不是按省份编号算出来的

**这是最容易搞错的一条。** 很多文档和直觉都说「省份 id 编码在颜色里，`id = R + G*256 + B*65536`」。在这类 overhaul 上**不成立**。

**实测过程**

按公式反推时，20005 个颜色里只有 **149 个**落在合法 id 区间（1..40000）——公式明显不适用。

改为「definition.csv 的 RGB 列是否出现在位图里」验证：

```python
from PIL import Image
im = Image.open('provinces.bmp').convert('RGB')
cols = set(im.getdata())            # 20005 种颜色
rows = []
for line in open('definition.csv', encoding='utf-8', errors='replace'):
    c = line.strip().split(';')
    if len(c) >= 4 and c[0].isdigit():
        rows.append((int(c[0]), (int(c[1]), int(c[2]), int(c[3]))))
hit = sum(1 for _, rgb in rows if rgb in cols)
print(hit, len(rows), len(cols))    # 20005 / 20006 / 20005
```

结果 **20005 / 20005 全部命中**，位图颜色数也正好等于省份数 —— **双射确认**。

**做法**
新增省份时，随便挑一个**未被占用**的 RGB 写进 definition.csv，再把这个颜色画进位图即可。不需要任何编码计算。

**definition.csv 列格式**
```
id;R;G;B;type;coastal;terrain;continent
20006;137;42;99;land;true;plains;6
```
- 第 5 列 `type`：`land` / `sea` / `lake`
- 第 8 列 `continent`：数字（亚洲 = 6）

**这条列可以用来做海陆筛查**，比看颜色靠谱：
```python
land = {pid for pid, c in rows.items() if c[4] == 'land'}
```

---

## 15. `terrain.bmp` 必须保持索引（P）模式，写调色板索引而不是 RGB

**症状**
存成 RGB 后文件从 12.5 MB 变成 37.5 MB，且地形可能全错（新陆地渲染成海、或整块地形异常）。

**原因**
`terrain.bmp` 是 8 位索引图，**像素值是调色板索引**，调色板颜色对应 `common/terrain/*.txt` 里各类地形的 `color = { R G B }`。

**正确做法**
```python
terr = Image.open('terrain.bmp')        # 保持 P 模式
terr = terr.copy()                      # 直接 Image.open 出来的对象是 readonly
pal = terr.getpalette()
rgb2idx = {}
for i in range(len(pal) // 3):          # 调色板长度不一定是 256
    c = (pal[i*3], pal[i*3+1], pal[i*3+2])
    if c not in rgb2idx:
        rgb2idx[c] = i

TERRAIN = {'plains': (132,255,0), 'forest': (58,131,82), 'hills': (112,74,31)}
TIDX = {k: rgb2idx.get(v) for k, v in TERRAIN.items()}

tpx = terr.load()
tpx[x, y] = TIDX['plains']              # 写索引，不是元组
terr.save('terrain.bmp')                # 仍以 P 模式保存 → 12.5 MB
```

**两个坑**
- `len(pal) // 3` 可能小于 256，硬写 `range(256)` 会 `IndexError`
- `Image.open()` 返回的对象是 **readonly**，`putpixel` / `load()` 赋值前必须 `.copy()`

---

## 16. `heightmap.bmp` 的海平面与陆地高度

**实测值（某 overhaul）**

| 类型 | 高度值 |
|---|---|
| 海 | **89** |
| 陆地 | **102—115** |

**做法**
新陆地填 108—120，并叠加一点起伏，避免完全平坦：
```python
hv = 108 + int(6*math.sin(x*0.05) + 6*math.cos(y*0.04)) + random.randint(0, 4)
hpx[x, y] = max(96, min(140, hv))
```

**同第 15 条**，`heightmap.bmp` 是 `L`（灰度）模式，`Image.open` 后要 `.convert('L')` 才能写。

---

## 17. 省份划分用「最远点采样 + Voronoi」，不要用网格

**症状**
按矩形网格把岛分成 N 块时，**边缘的格子会退化**——实测出现过某个省只有 **1 个像素**。这种省会导致渲染异常、寻路异常。

**原因**
岛的轮廓是不规则多边形，网格的四个角大量落在形状外，只剩零星像素。

**正确做法：种子点从岛内像素里挑，再按最近距离分配**

```python
# 最远点采样：保证种子全在岛内且分布均匀
seeds = [island[len(island)//3]]
while len(seeds) < NPROV:
    best_p, best_d = None, -1.0
    for (x, y) in island:
        d = min((x-sx)**2 + (y-sy)**2 for sx, sy in seeds)
        if d > best_d:
            best_d, best_p = d, (x, y)
    seeds.append(best_p)

def cell_of(x, y):
    return min(range(len(seeds)),
               key=lambda i: (x-seeds[i][0])**2 + (y-seeds[i][1])**2)
```

**效果**：16 个省从 `[1, 501, 2125, …]`（有 1 像素省）变成 `[2555, 2737, 3263, …, 7036]`，全部可用。

**性能**：72k 像素 × 16 轮 ≈ 1.2M 次距离计算，纯 Python 约 10 秒，不需要 numpy。

---

## 18. 改动必须只落在「原本是海」的像素上

**症状**
新陆地画上去后，某个现有国家的领土被吃掉一块。

**原因**
岛屿的包围盒里可能压着现有的小岛或半岛。

**做法：上色前用「海省份颜色集合」做交集**

```python
sea_colors = set()
for row in rows:
    if row[4] == 'sea':
        sea_colors.add((row[1], row[2], row[3]))

island = [(x, y) for (x, y) in mask_pixels if prov.getpixel((x, y)) in sea_colors]
```

**验证脚本（改完必跑）**
```python
from PIL import Image, ImageChops
a = Image.open('原/provinces.bmp').convert('RGB')
b = Image.open('新/provinces.bmp').convert('RGB')
diff = ImageChops.difference(a, b).convert('L')
print('改动像素', sum(diff.histogram()[1:]))

pa, pb = a.load(), b.load()
bad = sum(1 for y in range(y0, y1) for x in range(x0, x1)
          if pa[x, y] != pb[x, y] and pa[x, y] not in sea_colors)
print('改动到非海面的像素', bad)     # 必须是 0
```

实测输出：
```
改动像素 72396
改动到非海面的像素 0
```

---

## 19. 成熟 overhaul 自带 `map/`，所以新增省份必须自带整份位图

**症状 / 事实**
TNO 这类 mod 自己就带 `map/provinces.bmp`、`definition.csv`、`terrain.bmp`、`heightmap.bmp` 等整套地图文件（它本身就是地图 mod）。所以子 mod 要改地图，只能**整份携带改过的副本**，靠加载顺序覆盖。

**体积代价（实测）**

| 文件 | 大小 |
|---|---|
| `provinces.bmp` | 37.5 MB（RGB） |
| `terrain.bmp` | 12.5 MB（P 模式；存成 RGB 会变 37.5 MB） |
| `heightmap.bmp` | 12.5 MB（L 模式） |
| `definition.csv` | 0.7 MB |
| 合计 | **约 63 MB** |

**冲突面**
如果玩家还装了**另一个地图 mod**（比如 overhaul 的 Map Mod），同名的这三个位图会互相覆盖，谁后加载谁生效。

两种处理：
1. 要求玩家**不装**那个地图 mod（最省事）
2. 写一个 **rebase 脚本**：以对方位图为底，重新刷我们那几个省份的像素，而不是整份覆盖

**更新维护**：overhaul 本体更新地图后，这三个位图要重跑一次生成脚本。**所以生成脚本必须是「从原始位图重新生成」而不是「在旧输出上增量改」**，否则会积累错误。

---

## 20. 面积换算：用已知国家标定 km² / 像素

**问题**
「新国家面积要和 XX 差不多」这种需求，怎么落到像素数上？

**做法：拿一个面积确定的现有国家做标定**

```python
# 1) 数出该 tag 所有州的像素总数
def owner_area(tag):
    tot = 0
    for f in states:
        s = open(f).read()
        if owner_of(s) != tag: continue
        for p in provinces_of(s):
            tot += pixel_count.get(int(p), 0)
    return tot
```

实测：
```
日本本土  30031 像素 / 377975 km²  → 12.6 km²/像素
满洲国    66379 像素 / 800000 km²  → 12.1 km²/像素
```
两个数很接近（12.3 左右），说明该地图在东亚纬度带的像素-面积比是稳定的。

**目标 905500 km² → 72396 像素**。实际画出 72396 像素，误差 0。
