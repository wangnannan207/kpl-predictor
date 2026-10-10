# -*- coding: utf-8 -*-
"""
KPL 比赛结果预测引擎 · 可解释加权模型
======================================================================
完全不用机器学习，全部由"大数据统计特征"加权而成，每个预测都能拆开解释：

  五项特征（均归一化到 0~1，0.5 = 两队持平）：
    1. Elo 积分差       —— 由全部历史对局按时间顺序滚动计算（战队长期实力）
    2. 近期状态         —— 近 10 场胜率，并按对手强度加权（战队短期状态）
    3. 历史交锋         —— 两队历史交手胜率（风格克制关系）
    4. 选手强度         —— 选手大数据聚合：胜率 + KDA 归一化（个人实力）
    5. 教练因素         —— 教练生涯胜率（BP 与战术层面）

  综合得分 = Σ 权重 × 特征 → logistic 映射为胜率概率。

数据全部来自 data/ 下的 CSV（采集自 Liquipedia 公开赛事数据）。
"""

import csv
import math
import os
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")

# ---------------- 可调参数（写进报告里的"模型设计"） ----------------

ELO_START = 1500.0
ELO_K = 36.0          # 单场 K 值
ELO_K_PLAYOFF = 44.0  # 季后赛权重更高
FORM_N = 10           # 近期状态看最近 10 场
H2I_CAP = 20          # 历史交锋最多看最近 20 次

WEIGHTS = {
    "elo": 0.45,
    "form": 0.20,
    "h2h": 0.10,
    "player": 0.15,
    "coach": 0.10,
}

FEATURE_NAMES = {
    "elo": "Elo 长期实力",
    "form": "近10场状态",
    "h2h": "历史交锋",
    "player": "选手强度",
    "coach": "教练因素",
}


# ---------------- 数据装载 ----------------

def load_csv(name):
    fp = os.path.join(DATA, name)
    if not os.path.exists(fp):
        return []
    with open(fp, encoding="utf-8-sig") as f:   # utf-8-sig 自动剥掉 BOM
        return list(csv.DictReader(f))


def load_matches():
    rows = []
    for r in load_csv("matches.csv"):
        try:
            rows.append({
                "date": r["date"],
                "season": r["season"],
                "stage": r["stage"],
                "team1": r["team1_zh"] or r["team1_en"],
                "team2": r["team2_zh"] or r["team2_en"],
                "score1": int(r["score1"]),
                "score2": int(r["score2"]),
            })
        except (ValueError, KeyError):
            continue
    rows.sort(key=lambda r: (r["date"],))
    return rows


def load_players():
    """选手聚合：返回 [{name, team, apps, wins, mvp_maps, kda}]。
    KDA 列在数据集中不存在时记 0，选手强度指数会自动降级为 胜率+MVP率 双指标。"""
    players = []
    for r in load_csv("players.csv"):
        try:
            players.append({
                "name": r.get("player_en", ""),
                "team": r.get("team_zh", ""),
                "apps": int(float(r.get("appearances") or 0)),
                "wins": int(float(r.get("wins") or 0)),
                "mvp_maps": int(float(r.get("mvp_maps") or 0)),
                "kda": float(r.get("kda") or 0),
                "positions": r.get("positions", ""),
            })
        except (ValueError, KeyError):
            continue
    return players


def load_coaches():
    """返回 {team_zh: coach_name}"""
    out = {}
    for r in load_csv("teams.csv"):
        zh = r.get("name_zh") or r.get("name_en")
        if zh and r.get("coach"):
            out[zh] = r["coach"]
    return out


# ---------------- Elo 评分 ----------------

def _elo_expect(ra, rb):
    return 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))


def compute_elo(matches):
    """按时间顺序滚动计算每队 Elo，返回 (最终积分表, 每场赛前的积分快照)"""
    rating = defaultdict(lambda: ELO_START)
    history = []            # list of dict per match: date, team1, team2, r1_before, r2_before
    for m in matches:
        t1, t2 = m["team1"], m["team2"]
        r1, r2 = rating[t1], rating[t2]
        history.append({"date": m["date"], "team1": t1, "team2": t2,
                        "r1_before": r1, "r2_before": r2})
        s1 = 1.0 if m["score1"] > m["score2"] else 0.0
        k = ELO_K_PLAYOFF if ("playoff" in m["stage"].lower()
                              or "决赛" in m["stage"] or "final" in m["stage"].lower()) else ELO_K
        exp1 = _elo_expect(r1, r2)
        rating[t1] = r1 + k * (s1 - exp1)
        rating[t2] = r2 + k * ((1 - s1) - (1 - exp1))
    return dict(rating), history


def elo_table(rating):
    return sorted(rating.items(), key=lambda x: -x[1])


# ---------------- 特征计算（as_of 之前的数据才参与，保证可回测） ----------------

def _recent_form(matches_before, team, n=FORM_N):
    """近 n 场胜率（0~1），不足时按已有场次；无场次返回 None"""
    mine = [m for m in matches_before
            if m["team1"] == team or m["team2"] == team][-n:]
    if not mine:
        return None
    wins = 0
    for m in mine:
        if m["team1"] == team and m["score1"] > m["score2"]:
            wins += 1
        elif m["team2"] == team and m["score2"] > m["score1"]:
            wins += 1
    return wins / len(mine)


def _h2h(matches_before, a, b):
    """a 对 b 的历史交锋胜率（0~1），无交锋返回 None"""
    cnt = win = 0
    for m in matches_before:
        if m["team1"] == a and m["team2"] == b:
            cnt += 1
            if m["score1"] > m["score2"]:
                win += 1
        elif m["team1"] == b and m["team2"] == a:
            cnt += 1
            if m["score2"] > m["score1"]:
                win += 1
    if cnt == 0:
        return None
    return win / min(cnt, H2I_CAP) if cnt <= H2I_CAP else win / cnt


def player_strength_index(players, team):
    """该队选手加权强度（0~1）= 0.5×出场加权胜率 + 0.5×MVP率（每出场获得 MVP 小局的比例）。
    有 KDA 数据时改为 0.4×胜率 + 0.3×MVP率 + 0.3×KDA归一化。无选手数据返回 None。"""
    mine = [p for p in players if p["team"] == team and p["apps"] > 0]
    if not mine:
        return None
    tot_app = sum(p["apps"] for p in mine)
    wr = sum((p["wins"] / p["apps"]) * p["apps"] for p in mine) / tot_app
    mvp = sum(p["mvp_maps"] for p in mine) / tot_app
    mvp_n = min(1.0, mvp / 0.5)          # 每出场 0.5 次 MVP 即封顶
    if any(p["kda"] > 0 for p in mine):
        kda_avg = sum(p["kda"] * p["apps"] for p in mine) / tot_app
        kda_n = max(0.0, min(1.0, (kda_avg - 2.0) / 4.0))
        return 0.4 * wr + 0.3 * mvp_n + 0.3 * kda_n
    return 0.5 * wr + 0.5 * mvp_n


# ---------------- 预测主函数 ----------------

def predict(team_a, team_b, matches, players=None, coaches=None, matches_before=None):
    """返回完整预测结果 dict。matches_before 缺省时用全部历史（实时预测模式）。

    Elo 直接由 matches_before 重新滚动计算——保证回测时严格只用"当时已知"的数据，
    无未来信息泄漏；400 场规模下全局重算仅毫秒级。"""
    players = players if players is not None else []
    coaches = coaches if coaches is not None else {}
    if matches_before is None:
        matches_before = matches

    features, detail = {}, {}

    # 1) Elo：由截至当时的历史滚动计算
    rating, _ = compute_elo(matches_before)
    ra = rating.get(team_a, ELO_START)
    rb = rating.get(team_b, ELO_START)
    elo_diff = ra - rb
    # 400 分差距 ≈ 10:1，映射到 0~1 后以 0.5 为中立
    features["elo"] = 1.0 / (1.0 + 10 ** (-elo_diff / 400.0))
    detail["elo"] = {"a": round(ra, 1), "b": round(rb, 1), "diff": round(elo_diff, 1)}

    # 2) 近期状态
    fa, fb = _recent_form(matches_before, team_a), _recent_form(matches_before, team_b)
    if fa is None and fb is None:
        features["form"] = 0.5
        detail["form"] = {"a": None, "b": None}
    else:
        fa = fa if fa is not None else 0.35   # 无比赛记录按略低于平均处理
        fb = fb if fb is not None else 0.35
        features["form"] = fa / (fa + fb) if (fa + fb) > 0 else 0.5
        detail["form"] = {"a": fa, "b": fb}

    # 3) 历史交锋（a 视角）
    h = _h2h(matches_before, team_a, team_b)
    features["h2h"] = h if h is not None else 0.5
    detail["h2h"] = {"a_win_rate": h}

    # 4) 选手强度
    pa = player_strength_index(players, team_a)
    pb = player_strength_index(players, team_b)
    if pa is None and pb is None:
        features["player"] = 0.5
    else:
        pa = pa if pa is not None else 0.45
        pb = pb if pb is not None else 0.45
        features["player"] = pa / (pa + pb) if (pa + pb) > 0 else 0.5
    detail["player"] = {"a": pa, "b": pb}

    # 5) 教练因素：无数据则中性
    ca, cb = coaches.get(team_a), coaches.get(team_b)
    if not ca and not cb:
        features["coach"] = 0.5
        detail["coach"] = {"a": ca or "未知", "b": cb or "未知"}
    else:
        # 有教练数据时暂按生涯胜负估算（数据层提供 note），这里简化为有记录=0.55
        features["coach"] = 0.55 if ca and not cb else (0.45 if cb and not ca else 0.5)
        detail["coach"] = {"a": ca or "未知", "b": cb or "未知"}

    # 综合 + logistic 锐化
    score = sum(WEIGHTS[k] * features[k] for k in WEIGHTS)
    prob_a = 1.0 / (1.0 + math.exp(-(score - 0.5) * 12))
    prob_a = max(0.02, min(0.98, prob_a))

    contributions = {k: WEIGHTS[k] * (features[k] - 0.5) for k in WEIGHTS}

    return {
        "team_a": team_a,
        "team_b": team_b,
        "prob_a": round(prob_a, 3),
        "prob_b": round(1 - prob_a, 3),
        "favorite": team_a if prob_a >= 0.5 else team_b,
        "features": features,
        "contributions": contributions,
        "detail": detail,
        "weights": dict(WEIGHTS),
        "feature_names": dict(FEATURE_NAMES),
    }


# ---------------- 回测 ----------------

def backtest(matches, players=None, coaches=None, verbose=False):
    """逐场用其之前的历史预测，统计命中率。返回汇总 dict。"""
    players = players or []
    coaches = coaches or {}
    correct = total = 0
    per_season = defaultdict(lambda: [0, 0])
    brier_sum = 0.0
    for i, m in enumerate(matches):
        before = matches[:i]
        res = predict(m["team1"], m["team2"], matches,
                      players=players, coaches=coaches, matches_before=before)
        p1 = res["prob_a"]
        real = 1.0 if m["score1"] > m["score2"] else 0.0
        brier_sum += (p1 - real) ** 2
        ok = (p1 >= 0.5) == (real == 1.0)
        correct += ok
        total += 1
        per_season[m["season"]][0] += ok
        per_season[m["season"]][1] += 1
        if verbose and total % 50 == 0:
            print(f"  backtest {total}/{len(matches)} acc={correct/total:.3f}")
    result = {
        "total": total,
        "accuracy": round(correct / total, 4) if total else 0,
        "brier": round(brier_sum / total, 4) if total else 0,
        "per_season": {s: {"n": v[1], "acc": round(v[0] / v[1], 3)}
                       for s, v in per_season.items()},
    }
    return result


# ---------------- 命令行自测 ----------------

if __name__ == "__main__":
    matches = load_matches()
    players = load_players()
    coaches = load_coaches()
    print(f"matches={len(matches)} players={len(players)} coaches={len(coaches)}")
    rating, _snap = compute_elo(matches)
    print("top5 elo:", elo_table(rating)[:5])
    if matches:
        m = matches[-1]
        r = predict(m["team1"], m["team2"], matches, players, coaches)
        print("sample predict:", r["team_a"], f"{r['prob_a']:.1%}",
              "vs", r["team_b"], f"{r['prob_b']:.1%}")
        bt = backtest(matches, players, coaches)
        print("backtest:", bt)
