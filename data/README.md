# KPL 比赛结果预测系统 — 数据集说明（Liquipedia 部分）

## 数据来源

- 来源：Liquipedia 王者荣耀（Honor of Kings）wiki，MediaWiki API（`action=parse`，gzip）
- 抓取时间：2026-10-10（UTC+8）
- 原始 JSON 全部保留在 `raw/`（match_* = 比赛页 wikitext+HTML；stats_* = 统计页 wikitext；
  search_* = 结构搜索结果）
- 处理脚本：`download.py` / `fetch_all.py` / `fetch_essential.py`（抓取）→
  `parse_data.py`（比赛/地图/队伍/选手）→ `build_extras.py`（阵容/风格）→ `verify.py`（验收）

## 当前覆盖（2026-10-10 收尾版）

| 赛季 | 阶段 | 场数 |
|---|---|---|
| 2026春 | Stage 1 / 2 / 3 / Playoffs | 45 / 45 / 30 / 12 |
| 2025夏 | Stage 1 / 2 / 3 / Playoffs | 45 / 45 / 30 / 12 |
| 2025春 | Stage 1 | 45 |
| **合计** | | **309 场**（verify.py 实测） |

已通过验收的事实：2026春决 苏州KSG 4-0 重庆狼队（2026-04-11）；
2025夏决 成都AG超玩会 4-1 北京WB（2025-09-07）。

## 文件说明（本目录下由本流水线生成）

- `matches.csv`（309 行数据）— season,stage,date,team1_sc,team2_sc,team1_en,team2_en,
  team1_zh,team2_zh,score1,score2,winner_zh,mvps,map_count,bestof；按 date 升序
- `maps.csv`（1275 行）— 小局数据：红蓝方、时长(秒)、winner、双方英雄(|连接)
- `teams.csv`（24 行）— shortcode,name_en,name_zh,coach,note（coach 列：因战队页未抓到，全部为空）
- `players.csv`（223 行）— player_en,team_en,team_zh,appearances,wins,mvp_maps,positions
- `rosters.csv`（75 行）— 每队最近阶段 Top5 选手（MVP+换人统计），position/player_zh 待选手页补齐
- `team_season_stats.csv`（45 行）— season,team_zh,match_w,match_l,map_w,map_l,win_rate
- `team_style.csv`（15 行）— team_zh,matches_played,avg_duration_sec,map1_win_rate,
  blue_win_rate,red_win_rate,hero_pool_size,top_heroes

（注：heroes.csv / official_*.csv / player_heroes.csv 为另一数据源，非本流水线产物。）

## 短代码 → 战队名映射方法

每页按文档顺序提取 wiki 源码 `{{TeamOpponent|...}}` 短代码序列，与渲染 HTML 中
match-row 单元格 `aria-label`（完整队名）序列一一配对；全部 9 个已抓页面数量校验一致，
无失配。

## 已知缺陷

1. **未完成抓取（Liquipedia 对本机 IP 长时间 429 全域名封禁，从 09:08 起持续 3+ 小时）**：
   - 缺 2025春 Stage 2/3/Playoffs（约 102 场）
   - 缺 2025年度总决赛 Breakout/Challenge/Knockout Stage（约 50-60 场）
   - 缺 2024春/夏全部（用户指示：连续失败可跳过）
   - 缺各 /Statistics 页（仅 2025夏/2026春部分已抓）
   - 缺战队页（coach 列因此为空）与选手个人页（rosters 的 position/zh 列为空）
   - `fetch_essential.py` 后台仍在以 150 秒间隔重试；解封后运行：
     `python fetch_essential.py all && python parse_data.py && python build_extras.py && python verify.py`
2. **未映射中文名的战队**（按任务要求留空并在报告列出）：
   Qing Jiu Club（情久）、To Champion Group（TCG）、Team WE（西安WE）、
   Undefeated United Gamers，影响约 90 场比赛的 zh 字段及聚合统计。
3. **Liquipedia 无选手维度统计数据**：/Statistics 只有英雄/时长统计，
   players.csv 的 appearances/wins 来自每场 MVP 名单与换人模板，非真实登场。
4. winner=0/缺失的小局跳过；无有效小局的比赛（未赛/TBD）整场跳过。
5. 部分 2025春页面英雄名为旧版英文别名（如 mozi/no7），与 2026 春页面命名
   （如 mozi→?）不完全统一，保留英文原名未做归一化。

## verify.py 输出（2026-10-10 收尾运行）

见项目根目录 `verify_out.txt`。3 个 FAIL 均为"数据未抓取"类
（2025春决、2025年度总决赛事实抽查 + 对应聚合一致性），非解析错误；
数据补齐后重跑 verify.py 应全部通过。
