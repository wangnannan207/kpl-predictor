# -*- coding: utf-8 -*-
"""
KPL PREDICTOR · 王者荣耀职业联赛赛前胜负预测（Streamlit 互动网页）
======================================================================
- 选择对阵双方 → 五维特征加权 → 胜率 + 可解释拆解 + 对阵情报
- 赛程 / 排行榜 / 选手名单：调用 KPL 官网（kpl.qq.com）背后的 TGA 公开接口
- 视觉：参照 KPL 官网的浅色明亮风格（王者蓝 · 白底卡片 · 圆形头像）
"""

import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from predictor import (
    load_matches, load_players, load_coaches, compute_elo, elo_table,
    predict, backtest, WEIGHTS, FEATURE_NAMES, ELO_START,
)
import analytics

st.set_page_config(page_title="KPL PREDICTOR · 赛前胜负预测", page_icon="⚔",
                   layout="wide", initial_sidebar_state="collapsed")

BLUE, BLUE_DK, BLUE_LT = "#4A5BD7", "#2F3DA8", "#EEF1FD"
RED, RED_LT = "#E5484D", "#FDECEC"
GOLD = "#D9A441"
INK, GRAY, BORDER = "#1F2430", "#6B7280", "#E8ECF7"
CARD_SHADOW = "0 2px 12px rgba(47,61,168,.06)"

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DATA_READY = os.path.exists(os.path.join(DATA_DIR, "matches.csv"))

# 官网队名 → 数据集队名（官网 2026 赛季改用新队名/新主场名）
OFFICIAL_TO_DATA = {"KSG": "苏州KSG", "南通Hero久竞": "南京Hero久竞"}
DATA_TO_OFFICIAL = {v: k for k, v in OFFICIAL_TO_DATA.items()}
CURRENT_SID = "KPL2026S3"           # 2026 年度总决赛
CURRENT_SEASON_LABEL = "2026 年度总决赛"

# Liquipedia 罗马音英雄名 → 中文名（用于官网英雄头像，仅收录可确认项）
HERO_ZH = {
    "biron": "白起", "charlotte": "夏洛特", "arli": "公孙离",
    "taiyi zhenren": "太乙真人", "su lie": "苏烈", "cao cao": "曹操",
    "nuwa": "女娲", "lady sun": "孙尚香", "ge ya": "戈娅", "geya": "戈娅",
    "sikong zhen": "司空震", "master luban": "鲁班大师", "ao'yin": "敖隐",
    "guan yu": "关羽", "zhang fei": "张飞", "kong kong er": "空空儿",
    "agudo": "阿古朵", "dun": "盾山", "shen mengxi": "沈梦溪",
    "ma chao": "马超", "jing": "镜", "di renjie": "狄仁杰",
    "yang jian": "杨戬", "kaizer": "铠", "xiao qiao": "小乔",
    "ying zheng": "嬴政", "dolia": "朵莉亚", "lady zhen": "甄姬",
    "dharma": "达摩", "ukyo tachibana": "橘右京", "shieldun": "刘禅",
    "menki": "梦奇", "angela": "安琪拉", "meng tian": "蒙恬",
    "mai shiranui": "不知火舞", "yuhuan": "杨玉环", "mayene": "芈月",
    "chang'e": "嫦娥", "da qiao": "大乔", "heino": "海诺",
    "wu ze tian": "武则天", "ying": "影", "mozi": "墨子",
    "lian po": "廉颇", "shouyue": "百里守约", "wang zhaojun": "王昭君",
    "flowborn (tank)": "元流之子", "child tank": "元流之子",
    "pei": "裴擒虎", "erin": "艾琳", "xiao": "西施",
    "shangguan wan'er": "上官婉儿", "sun bin": "孙膑", "baili xuance": "百里玄策",
    "lan ling wang": "兰陵王", "zhuge liang": "诸葛亮", "guan yin ping": "关银屏",
}

# ---------------- 全局样式（KPL 官网浅色风） ----------------

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700;900&display=swap');
html, body, [class*="css"] { font-family: 'Noto Sans SC', 'Microsoft YaHei', sans-serif; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1.6rem; }

/* ---- 顶部横幅：官网蓝色渐变 ---- */
.hero {
    position: relative; border-radius: 14px; overflow: hidden;
    background: linear-gradient(115deg, #3D4ED3 0%, #5D6EE8 52%, #93A1F6 100%);
    padding: 34px 40px 30px 40px; margin-bottom: 8px; color: #FFFFFF;
    box-shadow: 0 10px 26px rgba(74,91,215,.28);
}
.hero::after {
    content: ""; position: absolute; right: -70px; top: -80px;
    width: 300px; height: 300px; border-radius: 50%;
    background: radial-gradient(circle, rgba(255,255,255,.14), transparent 65%);
}
.hero::before {
    content: ""; position: absolute; left: -50px; bottom: -110px;
    width: 260px; height: 260px; border-radius: 50%;
    background: radial-gradient(circle, rgba(255,255,255,.10), transparent 65%);
}
.hero .brand-en { font-size: 2.6rem; font-weight: 900; letter-spacing: 4px; position: relative; z-index: 1; }
.hero .brand-en .accent { color: #C9D3FF; }
.hero .brand-zh { font-size: 1.0rem; opacity: .95; letter-spacing: 6px; margin-top: 6px; font-weight: 700; position: relative; z-index: 1; }
.hero .meta { position: absolute; right: 40px; top: 32px; text-align: right;
              font-size: .78rem; line-height: 2.05; opacity: .96; z-index: 1; }
.hero .meta b { font-size: .95rem; }

/* ---- 章节标题：蓝块图标 + 蓝字 ---- */
.sec-head { display: flex; align-items: center; gap: 10px; margin: 26px 0 14px 0; }
.sec-ico { width: 22px; height: 22px; border-radius: 6px; flex: 0 0 22px;
           background: linear-gradient(135deg, #4A5BD7, #7B89F0);
           box-shadow: 0 3px 8px rgba(74,91,215,.35); }
.sec-txt { font-size: 1.22rem; font-weight: 900; color: #2F3DA8; letter-spacing: 2px; }
.sec-sub { font-size: .8rem; color: #8A93B8; margin-left: auto; letter-spacing: 1px; }

/* ---- 赛程卡片 ---- */
.match-card { background: #FFFFFF; border: 1px solid #E8ECF7; border-radius: 12px;
              padding: 11px 16px 9px 16px; margin-bottom: 10px; box-shadow: 0 2px 12px rgba(47,61,168,.06); }
.mc-top { font-size: .72rem; color: #8A93B8; display: flex; justify-content: space-between; margin-bottom: 7px; }
.mc-row { display: flex; align-items: center; }
.mc-team { flex: 1; display: flex; align-items: center; gap: 9px; font-weight: 700;
           font-size: .92rem; color: #1F2430; min-width: 0; }
.mc-team span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mc-team.right { justify-content: flex-end; }
.mc-logo { width: 34px; height: 34px; border-radius: 50%; object-fit: contain;
           background: #F4F6FB; border: 1px solid #EEF1FD; padding: 2px; flex: 0 0 34px; }
.mc-score { width: 92px; text-align: center; font-size: 1.28rem; font-weight: 900;
            color: #4A5BD7; font-variant-numeric: tabular-nums; }
.mc-score.pending { font-size: .82rem; color: #6B7280; font-weight: 700; line-height: 1.45; }
.mc-foot { font-size: .72rem; color: #B0B7D4; margin-top: 6px; text-align: center; }

/* ---- 结果面板 ---- */
.panel { background: #FFFFFF; border: 1px solid #E8ECF7; border-radius: 14px;
         padding: 20px 22px 16px 22px; height: 100%; box-shadow: 0 4px 16px rgba(47,61,168,.07); }
.panel.blue { border-top: 4px solid #4A5BD7; }
.panel.red { border-top: 4px solid #E5484D; }
.panel .side-tag { font-size: .7rem; letter-spacing: 3px; color: #8A93B8; font-weight: 700; }
.panel .tname { font-size: 1.4rem; font-weight: 900; color: #1F2430; margin: 6px 0 2px 0; }
.panel .prob { font-size: 2.7rem; font-weight: 900; line-height: 1.15; font-variant-numeric: tabular-nums; }
.panel .sub { font-size: .8rem; color: #6B7280; line-height: 1.85; }
.team-logo { border-radius: 50%; object-fit: contain; background: #F4F6FB;
             border: 1px solid #EEF1FD; padding: 3px; display: inline-block; }
.team-logo.init { background: linear-gradient(135deg, #4A5BD7, #7B89F0); color: #FFFFFF;
                  font-weight: 900; text-align: center; border: none; }

.vs-badge { display: inline-block; padding: 8px 24px; border-radius: 999px;
            background: linear-gradient(135deg, #4A5BD7, #7B89F0); color: #FFFFFF;
            font-size: 1.3rem; font-weight: 900; letter-spacing: 4px;
            box-shadow: 0 6px 16px rgba(74,91,215,.35); }
.vs-wrap { text-align: center; padding-top: 26px; }

/* ---- 排行榜 ---- */
.st-card { background: #FFFFFF; border: 1px solid #E8ECF7; border-radius: 14px;
           padding: 14px 18px 8px 18px; box-shadow: 0 2px 12px rgba(47,61,168,.06); height: 100%; }
.st-head { font-weight: 900; color: #2F3DA8; font-size: 1.02rem; letter-spacing: 2px;
           padding-bottom: 8px; border-bottom: 2px solid #EEF1FD; margin-bottom: 4px;
           display: flex; justify-content: space-between; align-items: baseline; }
.st-head .tag { font-size: .7rem; color: #B0B7D4; font-weight: 700; letter-spacing: 1px; }
.st-row { display: flex; align-items: center; gap: 10px; padding: 8px 2px; border-bottom: 1px solid #F4F6FB; }
.st-row:last-child { border-bottom: none; }
.st-rank { width: 30px; font-size: 1.02rem; font-weight: 900; color: #B0B7D4; }
.st-rank.gold { color: #D9A441; } .st-rank.silver { color: #9AA6C8; } .st-rank.bronze { color: #C98A5A; }
.st-logo { width: 30px; height: 30px; border-radius: 50%; object-fit: contain;
           background: #F4F6FB; border: 1px solid #EEF1FD; padding: 2px; flex: 0 0 30px; }
.st-name { flex: 1; font-weight: 700; font-size: .92rem; color: #1F2430; }
.st-wl { font-weight: 900; color: #1F2430; font-variant-numeric: tabular-nums; font-size: .92rem; }
.st-net { font-size: .74rem; color: #8A93B8; width: 58px; text-align: right; }

/* ---- 选手卡 ---- */
.pl-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(132px, 1fr)); gap: 12px; }
.pl-card { background: #FFFFFF; border: 1px solid #E8ECF7; border-radius: 12px;
           padding: 16px 8px 12px 8px; text-align: center; box-shadow: 0 2px 10px rgba(47,61,168,.05); }
.pl-photo { width: 82px; height: 82px; border-radius: 50%; object-fit: cover;
            border: 3px solid #EEF1FD; background: #F4F6FB; }
.pl-name { font-weight: 900; font-size: .95rem; margin-top: 9px; color: #1F2430; }
.pl-team { font-size: .72rem; color: #8A93B8; margin-top: 2px; }

/* ---- 英雄池 ---- */
.hero-cell { display: inline-block; text-align: center; width: 62px; margin: 0 3px 8px 0; vertical-align: top; }
.hero-ava { width: 50px; height: 50px; border-radius: 10px; border: 1px solid #E8ECF7; }
.hero-nm { font-size: .68rem; color: #6B7280; line-height: 1.35; margin-top: 3px; }

/* ---- 通用行 / 徽标 ---- */
.row-line { display: flex; justify-content: space-between; align-items: center;
            padding: 7px 10px; border-bottom: 1px solid #F1F4FC; font-size: .88rem; color: #1F2430; }
.row-line:last-child { border-bottom: none; }
.row-line .k { color: #8A93B8; font-size: .78rem; letter-spacing: 1px; }
.wl { display: inline-block; width: 25px; height: 25px; line-height: 25px; text-align: center;
      font-size: .76rem; font-weight: 700; margin-right: 5px; border-radius: 6px; }
.wl.w { color: #2F3DA8; background: #EEF1FD; border: 1px solid #C9D3FF; }
.wl.l { color: #C46A6E; background: #FDECEC; border: 1px solid #F6C9CB; }
.chip { display: inline-block; padding: 3px 11px; margin: 3px 5px 0 0; border: 1px solid #E8ECF7;
        color: #4A5BD7; font-size: .78rem; border-radius: 999px; background: #F7F9FE; font-weight: 700; }
.mini { font-size: .84rem; font-weight: 900; color: #2F3DA8; letter-spacing: 2px; margin: 16px 0 6px 0; }
.note { font-size: .78rem; color: #B0B7D4; }
.rank-pill { display: inline-block; padding: 1px 8px; border-radius: 999px; font-size: .7rem;
             font-weight: 900; color: #FFFFFF; background: linear-gradient(135deg, #E8B54A, #D9A441);
             vertical-align: middle; margin-left: 6px; }

/* ---- 按钮 / 页签 / 表格 ---- */
.stButton > button { background: linear-gradient(135deg, #4A5BD7, #7B89F0); color: #FFFFFF;
    border: none; border-radius: 10px; font-weight: 900; font-size: 1.05rem; letter-spacing: 8px;
    padding: .62rem 1rem; box-shadow: 0 6px 18px rgba(74,91,215,.35); transition: filter .12s, transform .12s; }
.stButton > button:hover { filter: brightness(1.08); transform: translateY(-1px); color: #FFFFFF; }
div[data-testid="stTabs"] [data-baseweb="tab-list"] { gap: 6px; background: #F4F6FB;
    border: 1px solid #E8ECF7; border-radius: 10px; padding: 5px; }
div[data-testid="stTabs"] button[data-baseweb="tab"] { color: #8A93B8; font-weight: 700; letter-spacing: 2px;
    font-size: .92rem; padding: 9px 18px; border-radius: 8px; }
div[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] { color: #FFFFFF !important;
    background: linear-gradient(135deg, #4A5BD7, #7B89F0); box-shadow: 0 3px 10px rgba(74,91,215,.3); }
.rank-row { display: flex; align-items: baseline; padding: 9px 12px; border-bottom: 1px solid #F1F4FC; }
.rank-row:last-child { border-bottom: none; }
.rank-row .n { font-size: 1.3rem; font-weight: 900; width: 44px; color: #4A5BD7; }
.rank-row .t { flex: 1; color: #1F2430; font-weight: 700; }
.rank-row .v { color: #4A5BD7; font-weight: 900; font-variant-numeric: tabular-nums; }
[data-testid="stDataFrame"] { background: #FFFFFF; border: 1px solid #E8ECF7; border-radius: 12px; }

.footer { margin-top: 44px; padding: 16px 4px 6px 4px; border-top: 1px solid #E8ECF7;
          font-size: .76rem; color: #B0B7D4; letter-spacing: 2px; text-align: center; }

/* ---- 当前赛季胜率面板 ---- */
.wr-card { background: #FFFFFF; border: 1px solid #E8ECF7; border-radius: 14px;
           padding: 22px 26px 18px 26px; box-shadow: 0 2px 12px rgba(47,61,168,.06); }
.wr-grid { display: flex; align-items: stretch; }
.wr-item { flex: 1; text-align: center; padding: 4px 6px; }
.wr-label { font-size: .82rem; color: #6B7280; font-weight: 500; margin-bottom: 8px; }
.wr-val { font-size: 1.6rem; font-weight: 900; color: #1F2430; font-variant-numeric: tabular-nums; }
.wr-val .pct { font-size: 1rem; font-weight: 700; color: #6B7280; }
.wr-div { width: 1px; background: #EEF1FD; margin: 6px 4px; }
.wr-pill { display: inline-block; padding: 2px 9px; border-radius: 999px; font-size: .7rem;
           font-weight: 900; color: #FFFFFF; background: linear-gradient(135deg, #E8B54A, #D9A441);
           vertical-align: middle; margin-left: 7px; }
.wr-pill.blue { background: linear-gradient(135deg, #5D6EE8, #4A5BD7); }
.wr-note { font-size: .72rem; color: #B0B7D4; margin-top: 12px; text-align: right; }

/* ---- 选手档案弹窗 ---- */
.pd-head { display: flex; gap: 26px; align-items: flex-start; }
.pd-photo { width: 128px; height: 128px; border-radius: 50%; object-fit: cover;
            border: 4px solid #EEF1FD; background: #F4F6FB; flex: 0 0 128px; }
.pd-name { font-size: 1.5rem; font-weight: 900; color: #1F2430; }
.pd-team { font-size: .8rem; color: #4A5BD7; font-weight: 700; margin: 4px 0 12px 0; }
.pd-line { display: flex; gap: 12px; font-size: .85rem; color: #1F2430;
           padding: 5px 0; border-bottom: 1px dashed #E8ECF7; min-width: 280px; }
.pd-line .k { color: #8A93B8; width: 64px; flex: 0 0 64px; }
.pd-sec { font-size: .82rem; font-weight: 900; color: #2F3DA8; letter-spacing: 2px; margin: 20px 0 10px 0; }
.pd-stats { display: flex; gap: 8px; }
.pd-stat { flex: 1; text-align: center; background: #F7F9FE; border: 1px solid #EEF1FD;
           border-radius: 10px; padding: 12px 4px 9px 4px; }
.pd-num { font-size: 1.35rem; font-weight: 900; color: #D9A441; font-variant-numeric: tabular-nums; }
.pd-num small { font-size: .78rem; font-weight: 700; }
.pd-lb { font-size: .72rem; color: #6B7280; margin-top: 3px; }
.pd-pill { display: inline-block; padding: 1px 7px; border-radius: 999px; font-size: .66rem;
           font-weight: 900; color: #FFFFFF; background: linear-gradient(135deg, #5D6EE8, #4A5BD7);
           vertical-align: middle; margin-left: 4px; }
.pd-bar-row { display: flex; align-items: center; gap: 10px; margin: 7px 0; }
.pd-bar-k { width: 60px; flex: 0 0 60px; font-size: .8rem; color: #6B7280; }
.pd-bar { flex: 1; height: 10px; background: #EEF1FD; border-radius: 999px; overflow: hidden; }
.pd-bar i { display: block; height: 100%; border-radius: 999px; }
.pd-bar-v { width: 52px; text-align: right; font-size: .8rem; font-weight: 900; color: #1F2430;
            font-variant-numeric: tabular-nums; }
.hr-row { display: flex; align-items: center; gap: 10px; padding: 6px 2px; border-bottom: 1px solid #F4F6FB; }
.hr-row:last-child { border-bottom: none; }
.hr-ava { width: 34px; height: 34px; border-radius: 8px; border: 1px solid #E8ECF7; flex: 0 0 34px; }
.hr-name { flex: 1; font-weight: 700; font-size: .9rem; color: #1F2430; }
.hr-pos { font-size: .7rem; color: #8A93B8; width: 44px; }
.hr-cnt { font-weight: 900; color: #1F2430; font-size: .9rem; width: 64px; text-align: right;
          font-variant-numeric: tabular-nums; }
.hr-wr { font-weight: 900; width: 56px; text-align: right; font-variant-numeric: tabular-nums; }
"""
st.markdown("<style>" + CSS + "</style>", unsafe_allow_html=True)


# ---------------- 数据 ----------------

@st.cache_data(show_spinner=False)
def get_data():
    matches = load_matches()
    players = load_players()
    coaches = load_coaches()
    rating, _ = compute_elo(matches)
    return matches, players, coaches, rating


@st.cache_data(show_spinner=False)
def get_maps():
    return analytics._load("maps.csv")


@st.cache_data(show_spinner=False)
def get_backtest(_k):
    matches, players, coaches, _ = get_data()
    return backtest(matches, players, coaches)


def _safe_csv(name):
    try:
        return predictor_load(name)
    except FileNotFoundError:
        return []


def predictor_load(name):
    from predictor import load_csv
    return load_csv(name)


@st.cache_data(show_spinner=False)
def get_official():
    """官网数据：赛程 / 排行榜 / 选手名单 / 英雄头像索引 / 选手赛季表现 / 英雄榜。"""
    schedule = _safe_csv("official_schedule.csv")
    standings = _safe_csv("official_standings.csv")
    oplayers = _safe_csv("official_players.csv")
    heroes = _safe_csv("heroes.csv")
    perf = _safe_csv("official_player_perf.csv")
    hero_rank = _safe_csv("official_hero_rank.csv")
    mvp_rank = _safe_csv("official_mvp.csv")
    player_heroes = _safe_csv("player_heroes.csv")
    avatar = {h["cname"]: h["avatar"] for h in heroes if h.get("cname")}
    logos = {}
    for m in schedule:
        for nk, lk in (("hname", "hlogo"), ("gname", "glogo")):
            nm, lg = (m.get(nk) or "").strip(), (m.get(lk) or "").strip()
            if nm and lg and nm != "待定":
                logos[nm] = lg
    for s in standings:
        nm, lg = (s.get("team_name") or "").strip(), (s.get("logo") or "").strip()
        if nm and lg and nm != "待定":
            logos.setdefault(nm, lg)
    return schedule, standings, oplayers, avatar, logos, perf, hero_rank, mvp_rank, player_heroes


if not DATA_READY:
    st.error("未找到 data/matches.csv 数据集，请先完成数据采集。")
    st.stop()

matches, players, coaches, rating = get_data()
maps_rows = get_maps()
rosters = analytics.load_rosters()
ctx = analytics.season_context(matches)
teams = sorted({m["team1"] for m in matches} | {m["team2"] for m in matches})
schedule, standings, oplayers, hero_avatar, team_logos, perf_rows, hero_rank_rows, mvp_rows, player_hero_rows = get_official()


# ---------------- 工具函数 ----------------

def sec_head(title, sub=""):
    sub_html = f'<span class="sec-sub">{sub}</span>' if sub else ""
    return (f'<div class="sec-head"><span class="sec-ico"></span>'
            f'<span class="sec-txt">{title}</span>{sub_html}</div>')


def logo_img(data_team, size=34, css="mc-logo"):
    """数据集队名 → 官网圆形队标；没有则回退为首字色块。"""
    off = DATA_TO_OFFICIAL.get(data_team, data_team)
    url = team_logos.get(off) or team_logos.get(data_team, "")
    if url:
        return (f'<img class="{css}" style="width:{size}px;height:{size}px" '
                f'src="{url}">')
    return (f'<span class="team-logo init" style="width:{size}px;height:{size}px;'
            f'line-height:{size}px;font-size:{int(size * .42)}px">{data_team[:1]}</span>')


def hero_cells(profile):
    """招牌英雄 → 官网英雄头像 + 场次胜率。入参为 hero_profile 返回的字典。"""
    top_heroes = (profile or {}).get("top") or []
    if not top_heroes:
        return '<span class="note">英雄数据采集中</span>'
    out = []
    for h, cnt, wr in top_heroes:
        zh = HERO_ZH.get(h.strip().lower())
        ava = hero_avatar.get(zh, "") if zh else ""
        if ava:
            out.append(f'<span class="hero-cell"><img class="hero-ava" src="{ava}" title="{zh}">'
                       f'<div class="hero-nm">{zh}<br>{cnt}局 · {wr:.0%}</div></span>')
        else:
            out.append(f'<span class="chip">{h} ×{cnt} · {wr:.0%}</span>')
    return "".join(out)


# ---------------- Hero ----------------

st.markdown(f"""
<div class="hero">
  <div class="meta">
    当前赛季　<b>{CURRENT_SEASON_LABEL}</b><br>
    收录对局　<b>{len(matches)} 场</b><br>
    数据截止　<b>{ctx['latest_date'] if ctx else '—'}</b>
  </div>
  <div class="brand-en">KPL <span class="accent">PREDICTOR</span></div>
  <div class="brand-zh">王者荣耀职业联赛 · 赛前胜负预测</div>
</div>
""", unsafe_allow_html=True)


# ---------------- 近期赛程（官网数据） ----------------

def fmt_md(t):
    """2026-10-17 20:00:00 → 10月17日 20:00"""
    try:
        d, tm = t.split(" ")
        y, mo, da = d.split("-")
        return f"{int(mo)}月{int(da)}日 {tm[:5]}"
    except Exception:
        return t or "—"


def match_card_html(m):
    h, g = (m.get("hname") or "").strip(), (m.get("gname") or "").strip()
    if not h or not g or h == "待定" or g == "待定":
        return ""
    hl, gl = team_logos.get(h, ""), team_logos.get(g, "")
    stage = m.get("stage_name") or ""
    region = m.get("region") or ""
    bo = m.get("bo_total") or ""
    top = f"{stage} · {region} · BO{bo}" if region else f"{stage} · BO{bo}"
    h_img = (f'<img class="mc-logo" src="{hl}">' if hl else
             f'<span class="team-logo init" style="width:34px;height:34px;line-height:34px;font-size:14px">{h[:1]}</span>')
    g_img = (f'<img class="mc-logo" src="{gl}">' if gl else
             f'<span class="team-logo init" style="width:34px;height:34px;line-height:34px;font-size:14px">{g[:1]}</span>')
    if (m.get("match_state") or "") == "4":
        mid = (f'<div class="mc-score">{m.get("host_score", "0")} : '
               f'{m.get("guest_score", "0")}</div>')
        foot = f'{fmt_md(m.get("match_time", ""))} 已结束'
    else:
        mid = f'<div class="mc-score pending">{fmt_md(m.get("match_time", ""))}</div>'
        foot = "未开赛 · 敬请期待"
    return (f'<div class="match-card"><div class="mc-top"><span>{top}</span>'
            f'<span>{fmt_md(m.get("match_time", ""))}</span></div>'
            f'<div class="mc-row"><div class="mc-team">{h_img}<span>{h}</span></div>'
            f'{mid}<div class="mc-team right"><span>{g}</span>{g_img}</div></div>'
            f'<div class="mc-foot">{foot}</div></div>')


cur_matches = [m for m in schedule if (m.get("scheduleid") or "").startswith(CURRENT_SID)]
finished = sorted([m for m in cur_matches if (m.get("match_state") or "") == "4"],
                  key=lambda m: int(m.get("match_timestamp") or 0), reverse=True)[:8]
upcoming = sorted([m for m in cur_matches if (m.get("match_state") or "") != "4"
                   and (m.get("hname") or "") != "待定"],
                  key=lambda m: int(m.get("match_timestamp") or 0))[:8]

st.markdown(sec_head("近期赛程", f"{CURRENT_SEASON_LABEL} · 数据来自 KPL 官网"),
            unsafe_allow_html=True)
if cur_matches:
    s1, s2 = st.columns(2)
    with s1:
        st.markdown('<div class="mini" style="margin-top:4px">近期赛果</div>',
                    unsafe_allow_html=True)
        body = "".join(match_card_html(m) for m in finished) or \
            '<div class="match-card"><div class="mc-foot">本赛季暂未产生赛果</div></div>'
        st.markdown(body, unsafe_allow_html=True)
    with s2:
        st.markdown('<div class="mini" style="margin-top:4px">即将开赛</div>',
                    unsafe_allow_html=True)
        body = "".join(match_card_html(m) for m in upcoming) or \
            '<div class="match-card"><div class="mc-foot">赛程数据采集中</div></div>'
        st.markdown(body, unsafe_allow_html=True)
else:
    st.info("官网赛程数据采集中，可运行 scrape_official.py 更新")


# ---------------- 预测输入 ----------------

st.markdown(sec_head("赛前预测", "五维特征加权 · 权重可在左侧栏调节"),
            unsafe_allow_html=True)
c1, c2, c3 = st.columns([2, 1, 2])
with c1:
    team_a = st.selectbox("蓝方", teams, index=0, label_visibility="collapsed")
with c2:
    st.markdown('<div class="vs-wrap"><span class="vs-badge">VS</span></div>',
                unsafe_allow_html=True)
with c3:
    team_b = st.selectbox("红方", teams, index=min(1, len(teams) - 1),
                          label_visibility="collapsed")

bc1, bc2, bc3 = st.columns([1, 1, 1])
with bc2:
    st.button("开 始 预 测", use_container_width=True)

if team_a == team_b:
    st.info("请选择两支不同的战队")
    st.stop()

# ---------------- 侧边栏 ----------------

with st.sidebar:
    st.header("模型权重")
    st.caption("拖动滑块调整五项特征占比，结果实时更新")
    w_elo = st.slider("Elo 长期实力", 0, 60, int(WEIGHTS["elo"] * 100)) / 100
    w_form = st.slider("近10场状态", 0, 60, int(WEIGHTS["form"] * 100)) / 100
    w_h2h = st.slider("历史交锋", 0, 40, int(WEIGHTS["h2h"] * 100)) / 100
    w_player = st.slider("选手强度", 0, 60, int(WEIGHTS["player"] * 100)) / 100
    w_coach = st.slider("教练因素", 0, 40, int(WEIGHTS["coach"] * 100)) / 100
    total_w = w_elo + w_form + w_h2h + w_player + w_coach
    if total_w == 0:
        st.error("权重不能全为 0")
        st.stop()
    import predictor
    predictor.WEIGHTS.update({"elo": w_elo / total_w, "form": w_form / total_w,
                              "h2h": w_h2h / total_w, "player": w_player / total_w,
                              "coach": w_coach / total_w})

# ---------------- 预测 ----------------

res = predict(team_a, team_b, matches, players, coaches)
pa, pb = res["prob_a"], res["prob_b"]
intel = analytics.matchup_intel(matches, maps_rows, team_a, team_b, players)
rank_map = {t: i + 1 for i, (t, _) in enumerate(elo_table(rating))}


def streak_txt(s):
    if s > 1:
        return f"连胜 {s} 场 · 气势正盛"
    if s == 1:
        return "上一场获胜"
    if s < -1:
        return f"连败 {abs(s)} 场 · 急需调整"
    if s == -1:
        return "上一场失利"
    return "暂无近期记录"


def wl_pills(results):
    if not results:
        return '<span class="note">暂无比赛记录</span>'
    return "".join(f'<span class="wl {"w" if r["win"] else "l"}">{"胜" if r["win"] else "负"}</span>'
                   for r in results)


def roster_html(team):
    rows = rosters.get(team, [])
    if not rows:
        return '<div class="row-line"><span class="k">数据采集中</span><span>—</span></div>'
    return "".join(
        f'<div class="row-line"><span class="k">{p["position"] or "未知位置"}</span>'
        f'<span>{p["player_zh"] or p["player_en"] or "—"}</span></div>'
        for p in rows)


def bp_html(bp, coach_name):
    name = coach_name or "未知"
    if not bp or bp.get("maps_played", 0) == 0:
        return (f'<div class="row-line"><span class="k">主教练</span><span>{name}</span></div>'
                f'<div class="row-line"><span class="k">BP 画像</span><span>数据采集中</span></div>')

    def pct(v):
        return f"{v:.0%}" if v is not None else "—"

    dur = bp.get("avg_duration_sec")
    dur_txt = f"{dur // 60}:{dur % 60:02d}" if dur else "—"
    return (f'<div class="row-line"><span class="k">主教练</span><span>{name}</span></div>'
            f'<div class="row-line"><span class="k">首局胜率</span><span>{pct(bp.get("map1_win_rate"))}</span></div>'
            f'<div class="row-line"><span class="k">蓝方胜率</span><span>{pct(bp.get("blue_win_rate"))}</span></div>'
            f'<div class="row-line"><span class="k">红方胜率</span><span>{pct(bp.get("red_win_rate"))}</span></div>'
            f'<div class="row-line"><span class="k">场均时长</span><span>{dur_txt}　{analytics.pace_label(dur)}</span></div>')


def section(title, sub=""):
    st.markdown(sec_head(title, sub), unsafe_allow_html=True)


# ---------------- 结果横幅 ----------------

k1, k2, k3 = st.columns([1, 1, 1])
with k1:
    st.markdown(f"""<div class="panel blue">
    <div style="display:flex;align-items:center;gap:12px">
      {logo_img(team_a, 56, "team-logo")}
      <div><div class="side-tag">蓝方 · BLUE SIDE</div>
      <div class="tname">{team_a}</div></div>
    </div>
    <div class="prob" style="color:{BLUE if pa >= 0.5 else GRAY};margin-top:8px">{pa:.0%}</div>
    <div class="sub">Elo {rating.get(team_a, ELO_START):.0f} ｜ 第 {rank_map.get(team_a, '—')} 位{' ｜ 占优' if pa >= 0.5 else ''}</div>
    <div style="margin-top:12px">{wl_pills(intel['recent_a'])}</div>
    <div class="sub" style="margin-top:6px">{streak_txt(intel['streak_a'])}</div></div>""",
    unsafe_allow_html=True)
with k2:
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=pa * 100,
        number={"suffix": "%", "font": {"color": INK, "size": 42}},
        title={"text": "蓝方胜算", "font": {"color": GRAY, "size": 13}},
        gauge={"axis": {"range": [0, 100], "tickcolor": BORDER,
                        "tickfont": {"color": GRAY, "size": 10}},
               "bar": {"color": BLUE if pa >= 0.5 else RED, "thickness": 0.28},
               "bgcolor": "#FFFFFF", "bordercolor": BORDER, "borderwidth": 1,
               "steps": [{"range": [0, 50], "color": "rgba(229,72,77,.07)"},
                         {"range": [50, 100], "color": "rgba(74,91,215,.08)"}]}))
    fig.update_layout(height=230, margin=dict(l=20, r=20, t=55, b=10),
                      paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)
    fav = res["favorite"]
    st.markdown(f"<div style='text-align:center;font-weight:900;color:{BLUE};"
                f"letter-spacing:3px;font-size:.95rem'>预测结论 · {fav} 占优</div>",
                unsafe_allow_html=True)
with k3:
    st.markdown(f"""<div class="panel red">
    <div style="display:flex;align-items:center;gap:12px">
      {logo_img(team_b, 56, "team-logo")}
      <div><div class="side-tag">红方 · RED SIDE</div>
      <div class="tname">{team_b}</div></div>
    </div>
    <div class="prob" style="color:{RED if pb > 0.5 else GRAY};margin-top:8px">{pb:.0%}</div>
    <div class="sub">Elo {rating.get(team_b, ELO_START):.0f} ｜ 第 {rank_map.get(team_b, '—')} 位{' ｜ 占优' if pb > 0.5 else ''}</div>
    <div style="margin-top:12px">{wl_pills(intel['recent_b'])}</div>
    <div class="sub" style="margin-top:6px">{streak_txt(intel['streak_b'])}</div></div>""",
    unsafe_allow_html=True)

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["对阵情报", "因素拆解", "战力排行", "历史交锋", "模型回测"])


# ---------------- Tab 1 对阵情报 ----------------

with tab1:
    i1, i2 = st.columns(2)
    with i1:
        st.markdown(f"""<div class="panel blue">
        <div style="display:flex;align-items:center;gap:12px">
          {logo_img(team_a, 44, "team-logo")}
          <div class="tname" style="margin:0">{team_a}</div>
        </div>
        <div class="mini">首发阵容</div>{roster_html(team_a)}
        <div class="mini">教练 · 选边 · 风格</div>{bp_html(intel['bp_a'], coaches.get(team_a))}
        <div class="mini">招牌英雄</div>{hero_cells(intel['heroes_a'])}
        </div>""", unsafe_allow_html=True)
    with i2:
        st.markdown(f"""<div class="panel red">
        <div style="display:flex;align-items:center;gap:12px">
          {logo_img(team_b, 44, "team-logo")}
          <div class="tname" style="margin:0">{team_b}</div>
        </div>
        <div class="mini">首发阵容</div>{roster_html(team_b)}
        <div class="mini">教练 · 选边 · 风格</div>{bp_html(intel['bp_b'], coaches.get(team_b))}
        <div class="mini">招牌英雄</div>{hero_cells(intel['heroes_b'])}
        </div>""", unsafe_allow_html=True)

    section("近期赛程实录")

    def recent_table(results):
        if not results:
            return pd.DataFrame([{"日期": "—", "赛事": "暂无记录", "对阵": "—", "结果": "—"}])
        return pd.DataFrame([{
            "日期": r["date"], "赛事": f'{r["season"]} · {r["stage"]}',
            "对阵": f'vs {r["opponent"]}（{r["score"]}）',
            "结果": "胜" if r["win"] else "负"} for r in reversed(results)])

    r1, r2 = st.columns(2)
    with r1:
        st.markdown(f'<div class="mini">{team_a} · 最近 {len(intel["recent_a"])} 场</div>',
                    unsafe_allow_html=True)
        st.dataframe(recent_table(intel["recent_a"]), use_container_width=True, height=230)
    with r2:
        st.markdown(f'<div class="mini">{team_b} · 最近 {len(intel["recent_b"])} 场</div>',
                    unsafe_allow_html=True)
        st.dataframe(recent_table(intel["recent_b"]), use_container_width=True, height=230)


# ---------------- Tab 2 因素拆解 ----------------

with tab2:
    f1, f2 = st.columns([3, 2])
    with f1:
        contrib = res["contributions"]
        cdf = pd.DataFrame({"因素": [FEATURE_NAMES[k] for k in contrib],
                            "贡献": [contrib[k] for k in contrib]}).sort_values("贡献")
        lim = max(abs(min(contrib.values())), abs(max(contrib.values()))) + 0.01
        fig = px.bar(cdf, x="贡献", y="因素", orientation="h", color="贡献",
                     color_continuous_scale=[(0, RED), (0.5, "#C9D3FF"), (1, BLUE)],
                     range_x=[-lim, lim],
                     title="各因素贡献（正偏向蓝方 · 负偏向红方）")
        fig.update_layout(height=360, coloraxis_showscale=False,
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          font={"color": GRAY},
                          title_font={"color": INK})
        st.plotly_chart(fig, use_container_width=True)
    with f2:
        det = res["detail"]
        st.markdown(f"""<div class="panel">
        <div class="row-line"><span class="k">Elo 积分</span><span>{det['elo']['a']} vs {det['elo']['b']}（{det['elo']['diff']:+.0f}）</span></div>
        <div class="row-line"><span class="k">近10场状态</span><span>{(f"{det['form']['a']:.0%}" if det['form']['a'] is not None else "无记录")} vs {(f"{det['form']['b']:.0%}" if det['form']['b'] is not None else "无记录")}</span></div>
        <div class="row-line"><span class="k">历史交锋</span><span>{(f"蓝方胜率 {det['h2h']['a_win_rate']:.0%}" if det['h2h']['a_win_rate'] is not None else "无交手记录")}</span></div>
        <div class="row-line"><span class="k">选手强度</span><span>{(f"{det['player']['a']:.2f}" if det['player']['a'] is not None else "无数据")} vs {(f"{det['player']['b']:.2f}" if det['player']['b'] is not None else "无数据")}</span></div>
        <div class="row-line"><span class="k">主教练</span><span>{det['coach']['a']} vs {det['coach']['b']}</span></div>
        </div>""", unsafe_allow_html=True)
        st.caption("拖动左侧权重滑块，观察贡献变化")


# ---------------- Tab 3 战力排行 ----------------

with tab3:
    board = elo_table(rating)
    t1, t2 = st.columns([1, 1])
    with t1:
        st.markdown('<div class="mini">ELO 积分总榜</div>', unsafe_allow_html=True)
        rows_html = "".join(
            f'<div class="rank-row"><span class="n">{i + 1:02d}</span>'
            f'<span class="t">{t}</span><span class="v">{v:.0f}</span></div>'
            for i, (t, v) in enumerate(board))
        st.markdown(f'<div class="panel">{rows_html}</div>', unsafe_allow_html=True)
    with t2:
        mvp_rows = sorted(players, key=lambda p: (p.get("mvp_maps", 0), p.get("wins", 0)),
                          reverse=True)[:10]
        mvp_html = "".join(
            f'<div class="rank-row"><span class="n">{i + 1:02d}</span>'
            f'<span class="t">{p["name"]}<span style="font-size:.72rem;color:#8A93B8">　{p["team"]}</span></span>'
            f'<span class="v">{p["mvp_maps"]} 次 MVP</span></div>'
            for i, p in enumerate(mvp_rows))
        st.markdown('<div class="mini">选手 MVP 榜 Top 10</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="panel">{mvp_html}</div>', unsafe_allow_html=True)
        edf = pd.DataFrame(board, columns=["战队", "Elo"])
        fig = px.bar(edf.head(10), x="Elo", y="战队", orientation="h", color="Elo",
                     color_continuous_scale=[(0, "#C9D3FF"), (1, BLUE)],
                     title="战力榜 Top 10")
        fig.update_layout(height=380, yaxis={"autorange": "reversed"},
                          coloraxis_showscale=False, paper_bgcolor="rgba(0,0,0,0)",
                          plot_bgcolor="rgba(0,0,0,0)", font={"color": GRAY},
                          title_font={"color": INK})
        st.plotly_chart(fig, use_container_width=True)


# ---------------- Tab 4 历史交锋 ----------------

with tab4:
    h2h = [m for m in matches if {m["team1"], m["team2"]} == {team_a, team_b}]
    if h2h:
        rows = [{"日期": m["date"], "赛事": f'{m["season"]} · {m["stage"]}',
                 "对阵": f'{m["team1"]} {m["score1"]} : {m["score2"]} {m["team2"]}',
                 "胜方": m["team1"] if m["score1"] > m["score2"] else m["team2"]}
                for m in reversed(h2h[-20:])]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, height=380)
        aw = sum(1 for m in h2h if (m["team1"] == team_a and m["score1"] > m["score2"]) or
                 (m["team2"] == team_a and m["score2"] > m["score1"]))
        st.markdown(f'<div class="mini">总计 {len(h2h)} 次交手 —— {team_a} {aw} 胜 · {team_b} {len(h2h) - aw} 胜</div>',
                    unsafe_allow_html=True)
    else:
        st.info("两队在所采集的数据范围内没有交手记录")


# ---------------- Tab 5 模型回测 ----------------

with tab5:
    bt = get_backtest("static")
    m1, m2, m3 = st.columns(3)
    m1.metric("回测样本", f"{bt['total']} 场")
    m2.metric("命中率", f"{bt['accuracy']:.1%}")
    m3.metric("Brier 分数", f"{bt['brier']:.3f}")
    section("分赛季命中率")
    sdf = pd.DataFrame([{"赛季": s, "场次": v["n"], "命中率": v["acc"]}
                        for s, v in bt["per_season"].items()])
    fig = px.bar(sdf, x="赛季", y="命中率", color="命中率",
                 color_continuous_scale=[(0, "#C9D3FF"), (1, BLUE)],
                 range_y=[0, 1], text=sdf["命中率"].map(lambda x: f"{x:.0%}"))
    fig.update_layout(height=330, coloraxis_showscale=False,
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font={"color": GRAY}, title_font={"color": INK})
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("""<div class="panel">
<div class="mini" style="margin-top:0">模型说明</div>
<div class="sub">
一、电竞单赛季每队仅数十场样本，复杂模型易过拟合，Elo 类评分是国际电竞分析的主流做法；<br>
二、五项特征全部来自真实赛事数据，每项都可独立查验、独立解释；<br>
三、权重开放调节，便于做因素敏感性分析——把经验判断变成可以复算的账。
</div></div>""", unsafe_allow_html=True)


# ---------------- 赛季排行榜（官网数据） ----------------

section("赛季排行榜", f"{CURRENT_SEASON_LABEL} · 数据来自 KPL 官网")
if standings:
    def st_rows_html(rows):
        items = []
        for r in sorted(rows, key=lambda x: int(float(x.get("rank") or 99))):
            rank = int(float(r.get("rank") or 99))
            cls = ("gold" if rank == 1 else "silver" if rank == 2 else
                   "bronze" if rank == 3 else "")
            nm = r.get("team_name") or "—"
            lg = r.get("logo") or team_logos.get(nm, "")
            img = (f'<img class="st-logo" src="{lg}">' if lg else
                   f'<span class="team-logo init" style="width:30px;height:30px;line-height:30px;font-size:12px">{nm[:1]}</span>')
            items.append(
                f'<div class="st-row"><span class="st-rank {cls}">{rank}</span>{img}'
                f'<span class="st-name">{nm}</span>'
                f'<span class="st-wl">{r.get("win", "0")} - {r.get("lose", "0")}</span>'
                f'<span class="st-net">净胜 {r.get("net_points", "0")}</span></div>')
        return "".join(items)

    g1, g2 = st.columns(2)
    for col, grp, label in ((g1, "S", "S 组"), (g2, "A", "A 组")):
        rows = [r for r in standings if (r.get("match_group") or "") == grp]
        with col:
            st.markdown(f'<div class="st-card"><div class="st-head">{label}'
                        f'<span class="tag">BO5 擂台赛阶段</span></div>'
                        f'{st_rows_html(rows) or "<div class=st-row>数据采集中</div>"}'
                        f'</div>', unsafe_allow_html=True)
    if hero_rank_rows:
        st.markdown(f'<div class="mini">英雄排行榜 · {CURRENT_SEASON_LABEL} 登场数 Top 12</div>',
                    unsafe_allow_html=True)
        top_heroes = sorted(hero_rank_rows,
                            key=lambda h: -int(float(h.get("match_count") or 0)))[:12]
        hr_items = []
        for h in top_heroes:
            try:
                wr = float(h.get("win_cr") or 0) * 100
            except (TypeError, ValueError):
                wr = 0.0
            hid = h.get("hero_id", "")
            hr_items.append(
                f'<div class="hr-row">'
                f'<img class="hr-ava" src="https://game.gtimg.cn/images/yxzj/img201606/heroimg/{hid}/{hid}.jpg">'
                f'<span class="hr-name">{h.get("hero_name", "—")}</span>'
                f'<span class="hr-cnt">{h.get("match_count", "0")} 局</span>'
                f'<span class="hr-wr" style="color:{"#4A5BD7" if wr >= 50 else "#E5484D"}">{wr:.0f}%</span>'
                f'</div>')
        st.markdown(f'<div class="st-card">{"".join(hr_items)}</div>', unsafe_allow_html=True)
else:
    st.info("官网排行榜数据采集中，可运行 scrape_official.py 更新")


# ---------------- 战队数据（当前赛季胜率 + 大名单选手档案） ----------------

SEASON_LABEL = {"2025春": "2025 春季赛", "2025夏": "2025 夏季赛",
                "2026春": "2026 春季赛", "2026年度总决赛": "2026 年度总决赛"}


def _blank_stats():
    return dict(big=0, bw=0, bl=0, blue=0, bluew=0, red=0, redw=0)


def season_side_stats(season):
    """按小局数据计算每队：大场数/大场胜/负、蓝方场次/胜、红方场次/胜。"""
    stats = {}
    for m in matches:
        if m["season"] != season:
            continue
        for t, s, o in ((m["team1"], m["score1"], m["score2"]),
                        (m["team2"], m["score2"], m["score1"])):
            d = stats.setdefault(t, _blank_stats())
            d["big"] += 1
            if s > o:
                d["bw"] += 1
            else:
                d["bl"] += 1
    for r in maps_rows:
        if (r.get("season") or "") != season:
            continue
        t1, t2 = r.get("team1_zh", ""), r.get("team2_zh", "")
        try:
            w1 = int(r.get("winner") or 0) == 1
        except (ValueError, TypeError):
            continue
        s1 = (r.get("side1") or "").lower()
        s2 = (r.get("side2") or "").lower()
        for t, side, won in ((t1, s1, w1), (t2, s2, not w1)):
            if t not in stats:
                continue
            d = stats[t]
            if side == "blue":
                d["blue"] += 1
                d["bluew"] += 1 if won else 0
            elif side == "red":
                d["red"] += 1
                d["redw"] += 1 if won else 0

    def _rank(num_key, win_key):
        vals = sorted(
            (((d[win_key] / d[num_key]) if d[num_key] else -1), t)
            for t, d in stats.items() if d[num_key] >= 4)
        vals.reverse()
        return {t: i + 1 for i, (_, t) in enumerate(vals)}

    return stats, _rank("big", "bw"), _rank("blue", "bluew"), _rank("red", "redw")


panel_season = ctx["latest_season"] if ctx else ""
panel_label = SEASON_LABEL.get(panel_season, panel_season)
side_stats, big_rank, blue_rank, red_rank = ({}, {}, {}, {})
if panel_season:
    side_stats, big_rank, blue_rank, red_rank = season_side_stats(panel_season)


def wr_panel_html(team):
    d = side_stats.get(team)
    if not d or d["big"] == 0:
        return ('<div class="wr-card"><div class="wr-note">该队在 '
                + panel_label + ' 暂无比赛记录</div></div>')
    big_pct = d["bw"] / d["big"] if d["big"] else 0
    bl_pct = d["bluew"] / d["blue"] if d["blue"] else None
    rd_pct = d["redw"] / d["red"] if d["red"] else None

    def pill(rank_map):
        r = rank_map.get(team)
        return f'<span class="wr-pill">排名{r}</span>' if r else ""

    def pill_blue(rank_map):
        r = rank_map.get(team)
        return f'<span class="wr-pill blue">排名{r}</span>' if r else ""

    def pct_txt(v):
        return f"{v:.0%}" if v is not None else "—"

    return (f'<div class="wr-card"><div class="wr-grid">'
            f'<div class="wr-item"><div class="wr-label">比赛场数</div>'
            f'<div class="wr-val">{d["big"]}</div></div>'
            f'<div class="wr-item"><div class="wr-label">综合胜率</div>'
            f'<div class="wr-val">{big_pct:.0%}{pill(big_rank)}</div></div>'
            f'<div class="wr-div"></div>'
            f'<div class="wr-item"><div class="wr-label">蓝方次数</div>'
            f'<div class="wr-val">{d["blue"]}</div></div>'
            f'<div class="wr-item"><div class="wr-label">蓝方胜率</div>'
            f'<div class="wr-val">{pct_txt(bl_pct)}{pill_blue(blue_rank)}</div></div>'
            f'<div class="wr-div"></div>'
            f'<div class="wr-item"><div class="wr-label">红方次数</div>'
            f'<div class="wr-val">{d["red"]}</div></div>'
            f'<div class="wr-item"><div class="wr-label">红方胜率</div>'
            f'<div class="wr-val">{pct_txt(rd_pct)}{pill_blue(red_rank)}</div></div>'
            f'</div>'
            f'<div class="wr-note">蓝方 / 红方统计为小局口径 · {panel_label}</div></div>')


# ---- 选手档案：官网内部接口真实数据（本名 / 位置 / KDA / 参团率） ----
POS_LABEL = {"1": "对抗路", "2": "中路", "3": "发育路", "4": "打野", "5": "游走"}
POS_ORDER = {"对抗路": 0, "打野": 1, "中路": 2, "发育路": 3, "游走": 4}


def _pf(p, key):
    try:
        return float(p.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


_perf_rated = [p for p in perf_rows if int(float(p.get("Matchcount") or 0)) >= 3]
KDA_RANK = {p["player_id"]: i + 1
            for i, p in enumerate(sorted(_perf_rated, key=lambda x: -_pf(x, "KDA")))}
KP_RANK = {p["player_id"]: i + 1
           for i, p in enumerate(sorted(_perf_rated, key=lambda x: -_pf(x, "AVGPartacipationCR")))}


@st.dialog("选手档案", width="large")
def player_dialog(p):
    name = p.get("player_short_name", "—")
    real = (p.get("player_real_name") or "").strip()
    team_official = p.get("team_name", "")
    team_data = OFFICIAL_TO_DATA.get(team_official, team_official)
    pos = POS_LABEL.get(str(p.get("position", "")), "未知位置")
    pid = p.get("player_id", "")
    kda_p = KDA_RANK.get(pid)
    kp_p = KP_RANK.get(pid)
    title = f"{name}（{real}）" if real else name
    st.markdown(f"""<div class="pd-head">
      <img class="pd-photo" src="{p.get("player_logo", "")}">
      <div>
        <div class="pd-name">{title}</div>
        <div class="pd-team">{team_official} · {pos}</div>
        <div class="pd-line"><span class="k">出生日期</span><span>—</span></div>
        <div class="pd-line"><span class="k">籍　　贯</span><span>—</span></div>
        <div class="pd-line"><span class="k">登场时间</span><span>—</span></div>
      </div></div>""", unsafe_allow_html=True)

    st.markdown('<div class="pd-sec">赛季表现（2026 年度总决赛）</div>', unsafe_allow_html=True)
    st.markdown(f"""<div class="pd-stats">
      <div class="pd-stat"><div class="pd-num">{int(float(p.get("Matchcount") or 0))}<small> 局</small></div>
        <div class="pd-lb">登场</div></div>
      <div class="pd-stat"><div class="pd-num">{p.get("KDA", "—")}</div>
        <div class="pd-lb">KDA{('<span class="pd-pill">排名' + str(kda_p) + '</span>') if kda_p else ''}</div></div>
      <div class="pd-stat"><div class="pd-num">{int(float(p.get("TotalKill") or 0))}</div>
        <div class="pd-lb">总击杀</div></div>
      <div class="pd-stat"><div class="pd-num">{_pf(p, "AVGPartacipationCR"):.1f}<small>%</small></div>
        <div class="pd-lb">参团率{('<span class="pd-pill">排名' + str(kp_p) + '</span>') if kp_p else ''}</div></div>
    </div>""", unsafe_allow_html=True)

    def bar(label, val, color):
        w = min(max(val, 0.0), 60.0) / 60.0 * 100
        return (f'<div class="pd-bar-row"><span class="pd-bar-k">{label}</span>'
                f'<span class="pd-bar"><i style="width:{w:.0f}%;background:{color}"></i></span>'
                f'<span class="pd-bar-v">{val:.1f}%</span></div>')

    st.markdown('<div class="pd-sec">输出 · 承伤 · 经济占比</div>', unsafe_allow_html=True)
    st.markdown(bar("输出占比", _pf(p, "AVGHurtCR"), "#E5484D")
                + bar("承伤占比", _pf(p, "AVGBeHurtCr"), "#4A5BD7")
                + bar("经济占比", _pf(p, "AVGGoldCR"), "#D9A441"),
                unsafe_allow_html=True)

    st.markdown('<div class="pd-sec">招牌英雄</div>', unsafe_allow_html=True)
    mine = [h for h in player_hero_rows
            if (h.get("player_name") or "").strip() == name
            and (h.get("team_zh") or "").strip() in (team_official, team_data)]
    mine.sort(key=lambda h: -int(float(h.get("picks") or 0)))
    if mine:
        cells = []
        for h in mine[:5]:
            zh = (h.get("hero") or "").strip()
            ava = hero_avatar.get(zh, "")
            pk = (h.get("picks") or "").strip()
            wn = (h.get("wins") or "").strip()
            sub = f"{pk}局|{wn}胜" if pk else ""
            if ava:
                cells.append(f'<span class="hero-cell"><img class="hero-ava" src="{ava}" title="{zh}">'
                             f'<div class="hero-nm">{zh}<br>{sub}</div></span>')
            else:
                cells.append(f'<span class="chip">{zh} {sub}</span>')
        st.markdown("".join(cells), unsafe_allow_html=True)
        st.caption(f"英雄池 {len(mine)} 个 · 本赛季个人数据")
    else:
        st.markdown('<div class="note">该选手个人英雄池数据采集中（需从官网录入）。</div>',
                    unsafe_allow_html=True)
        pool = analytics.hero_profile(maps_rows, team_data)
        with st.expander(f"查看 {team_data} 战队已收录英雄池（{pool['pool_size']} 个 · 非个人数据）"):
            st.markdown(hero_cells(pool), unsafe_allow_html=True)


section("战队数据", f"当前赛季胜率 · 选手大名单 · {panel_label}")
sel_team = st.selectbox("选择战队", teams,
                      index=teams.index("成都AG超玩会") if "成都AG超玩会" in teams else 0,
                      label_visibility="collapsed")
st.markdown(wr_panel_html(sel_team), unsafe_allow_html=True)

sel_official = DATA_TO_OFFICIAL.get(sel_team, sel_team)
members = [p for p in perf_rows if p.get("team_name") == sel_official]
members.sort(key=lambda p: POS_ORDER.get(POS_LABEL.get(str(p.get("position", "")), ""), 9))
if members:
    st.markdown(f'<div class="mini">{sel_team} · 本赛季出战选手（{len(members)} 人 · 按位置排序）</div>',
                unsafe_allow_html=True)
    for start in range(0, len(members), 6):
        row_members = members[start:start + 6]
        cols = st.columns(len(row_members))
        for col, mem in zip(cols, row_members):
            pos = POS_LABEL.get(str(mem.get("position", "")), "")
            with col:
                st.markdown(f"""<div style="text-align:center">
                  <img class="pl-photo" src="{mem.get("player_logo", "")}">
                  <div class="pl-name" style="margin-top:8px">{mem.get("player_short_name", "—")}</div>
                  <div class="pl-team">{pos}</div></div>""",
                    unsafe_allow_html=True)
                if st.button("查看档案", key=f"pd_{mem.get('player_id', mem.get('player_short_name'))}",
                             use_container_width=True):
                    player_dialog(mem)
else:
    st.info("该队选手名单采集中（官网名单仅覆盖 2026 年度总决赛参赛队伍）")


st.markdown("""<div class="footer">
KPL PREDICTOR · 王者荣耀职业联赛赛前胜负预测 · 数据来自 LIQUIPEDIA 公开赛事数据与 KPL 官网公开接口 · 仅供学习交流
</div>""", unsafe_allow_html=True)
