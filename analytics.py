# -*- coding: utf-8 -*-
"""
对阵情报分析层 · 从比赛/小局/阵容数据提炼"看得懂"的情报
==============================================================
为网页"对阵情报室"提供：
  - 战队近期战绩走势（近 5 场 W/L、连胜/连败 = 心态量化代理指标）
  - 首发阵容（按位置：对抗路/打野/中路/发育路/游走）
  - 主教练与 BP 画像（首局胜率、红蓝方选边胜率）
  - 比赛风格（场均时长 → 闪电战/标准/持久战、英雄池深度、常用英雄）
全部基于 data/ 下的真实数据计算，字段缺失时优雅降级（返回 None 或空表）。
"""

import csv
import os
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")

POS_ORDER = ["对抗路", "打野", "中路", "发育路", "游走"]
POS_ALIAS = {
    "top": "对抗路", "top lane": "对抗路", "clash lane": "对抗路",
    "jungle": "打野", "jg": "打野",
    "mid": "中路", "mid lane": "中路", "middle": "中路",
    "farm": "发育路", "farm lane": "发育路", "adc": "发育路", "bot": "发育路",
    "roam": "游走", "support": "游走", "sup": "游走", "utility": "游走",
}


def _load(name):
    fp = os.path.join(DATA, name)
    if not os.path.exists(fp):
        return []
    with open(fp, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def normalize_pos(raw):
    if not raw:
        return ""
    return POS_ALIAS.get(raw.strip().lower(), raw.strip())


# ---------------- 近期战绩与心态代理指标 ----------------

def recent_results(matches, team, n=5):
    """近 n 场结果，最新在最后。返回 [{date, opponent, win, score, season, stage}]"""
    mine = [m for m in matches if m["team1"] == team or m["team2"] == team]
    out = []
    for m in mine[-n:]:
        win = (m["team1"] == team and m["score1"] > m["score2"]) or \
              (m["team2"] == team and m["score2"] > m["score1"])
        opp = m["team2"] if m["team1"] == team else m["team1"]
        out.append({"date": m["date"], "opponent": opp, "win": win,
                    "score": f"{m['score1']}-{m['score2']}",
                    "season": m["season"], "stage": m["stage"]})
    return out


def streak(matches, team):
    """当前连胜(正数)/连败(负数)，无比赛返回 0"""
    mine = [m for m in matches if m["team1"] == team or m["team2"] == team]
    if not mine:
        return 0
    s = 0
    for m in reversed(mine):
        win = (m["team1"] == team and m["score1"] > m["score2"]) or \
              (m["team2"] == team and m["score2"] > m["score1"])
        if s == 0 or (win and s > 0) or (not win and s < 0):
            s = s + 1 if win else s - 1
        else:
            break
    return s


# ---------------- 阵容 ----------------

def load_rosters():
    """{team: [{position, player_en, player_zh, games_played}, ...]} 按位置排序"""
    rows = _load("rosters.csv")
    out = defaultdict(list)
    for r in rows:
        team = r.get("team_zh", "")
        out[team].append({
            "position": normalize_pos(r.get("position", "")),
            "player_en": r.get("player_en", ""),
            "player_zh": r.get("player_zh", ""),
            "games": int(float(r.get("games_played") or 0)),
        })
    for team in out:
        out[team].sort(key=lambda p: POS_ORDER.index(p["position"])
                       if p["position"] in POS_ORDER else 99)
    return dict(out)


# ---------------- BP 与选边 ----------------

def bp_profile(maps_rows, team):
    """从小局数据计算 BP 画像：首局胜率 / 蓝方胜率 / 红方胜率 / 场均时长。
    返回 dict，任一指标无数据时为 None。"""
    map1, blue, red, dur = [], [], [], []
    for r in maps_rows:
        t1, t2 = r.get("team1_zh", ""), r.get("team2_zh", "")
        if team not in (t1, t2):
            continue
        try:
            win = int(r.get("winner") or 0)
        except ValueError:
            continue
        if win not in (1, 2):
            continue
        won = (win == 1) == (t1 == team)
        if r.get("map_no") == "1":
            map1.append(won)
        side = r.get("side1") if t1 == team else r.get("side2")
        if side == "blue":
            blue.append(won)
        elif side == "red":
            red.append(won)
        try:
            dur.append(int(float(r.get("length_seconds") or 0)))
        except ValueError:
            pass
    def rate(lst):
        return round(sum(lst) / len(lst), 3) if lst else None
    avg_dur = round(sum(dur) / len(dur)) if dur else None
    return {"map1_win_rate": rate(map1), "blue_win_rate": rate(blue),
            "red_win_rate": rate(red), "avg_duration_sec": avg_dur,
            "maps_played": len(map1)}


def pace_label(avg_sec):
    """场均时长 → 风格标签"""
    if avg_sec is None:
        return "数据不足"
    if avg_sec < 900:
        return "⚡ 闪电战偏好"
    if avg_sec < 1080:
        return "⏱ 标准节奏"
    if avg_sec < 1260:
        return "🛡 稳健运营"
    return "🐢 持久战大师"


# ---------------- 英雄池 ----------------

def hero_profile(maps_rows, team, topk=5):
    """{pool_size, top: [(hero, picks, win_rate), ...]}"""
    picks, wins = defaultdict(int), defaultdict(int)
    for r in maps_rows:
        t1, t2 = r.get("team1_zh", ""), r.get("team2_zh", "")
        if team not in (t1, t2):
            continue
        mine = r.get("heroes_t1", "") if t1 == team else r.get("heroes_t2", "")
        if not mine:
            continue
        try:
            won = (int(r.get("winner") or 0) == 1) == (t1 == team)
        except ValueError:
            won = False
        for h in mine.split("|"):
            h = h.strip()
            if h:
                picks[h] += 1
                wins[h] += 1 if won else 0
    total = sum(picks.values())
    top = sorted(picks.items(), key=lambda x: -x[1])[:topk]
    return {"pool_size": len(picks), "total_map_picks": total,
            "top": [(h, c, round(wins[h] / c, 2)) for h, c in top]}


# ---------------- 赛季上下文 ----------------

def season_context(matches):
    """数据覆盖的最新赛季/阶段 + 各赛季场数"""
    if not matches:
        return None
    latest = matches[-1]
    per = defaultdict(int)
    for m in matches:
        per[m["season"]] += 1
    return {"latest_season": latest["season"], "latest_stage": latest["stage"],
            "latest_date": latest["date"], "per_season": dict(per)}


# ---------------- 一键情报组装 ----------------

def matchup_intel(matches, maps_rows, team_a, team_b, players=None):
    """组装网页"对阵情报室"需要的全部内容"""
    players = players or []
    intel = {"recent_a": recent_results(matches, team_a),
             "recent_b": recent_results(matches, team_b),
             "streak_a": streak(matches, team_a),
             "streak_b": streak(matches, team_b),
             "bp_a": bp_profile(maps_rows, team_a),
             "bp_b": bp_profile(maps_rows, team_b),
             "heroes_a": hero_profile(maps_rows, team_a),
             "heroes_b": hero_profile(maps_rows, team_b)}
    # 选手个人近态（MVP 率、胜率）
    def pstat(team):
        mine = [p for p in players if p["team"] == team and p["apps"] > 0]
        out = []
        for p in mine:
            out.append({"name": p["name"], "apps": p["apps"],
                        "win_rate": round(p["wins"] / p["apps"], 2),
                        "mvp_rate": round(p["mvp_maps"] / p["apps"], 2) if p["apps"] else 0})
        return sorted(out, key=lambda x: -x["mvp_rate"])[:8]
    intel["players_a"] = pstat(team_a)
    intel["players_b"] = pstat(team_b)
    return intel
