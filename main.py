# -*- coding: utf-8 -*-
"""급식 월드컵 - 8강 토너먼트로 가장 맛있는 반찬을 뽑는 Streamlit 앱.

- 접속 정보: st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
- 저장 표: public.menu_duels (교사가 미리 만든 표에 그대로 연결, 새 표 생성 없음)
- 앱이 채우는 열: game_id, round, left_menu, right_menu, winner
  (id, created_at은 데이터베이스가 채움)
- 수정·삭제 기능 없음, 이름·학번·비밀번호는 받지 않음
"""

import random
import unicodedata
import uuid

import streamlit as st
from supabase import create_client

TABLE_NAME = "menu_duels"  # public 스키마 표. 스키마 이름은 붙이지 않는다.

MENUS = [
    "제육볶음",
    "간장찜닭",
    "가자미순살튀김",
    "돈육불백",
    "미트볼데리야끼볶음",
    "수육",
    "진미채고추장볶음",
    "치즈떡닭갈비",
]

ROUND_LABELS = {8: "8강", 4: "4강", 2: "결승"}
TOTAL_DUELS = 7  # 8강 4번 + 4강 2번 + 결승 1번

st.set_page_config(page_title="급식 월드컵", page_icon="🍱", layout="centered")


# ---------------------------------------------------------------------------
# 유틸리티
# ---------------------------------------------------------------------------
def clean_text(value: str) -> str:
    """한글이 깨지지 않도록 NFC로 정규화하고 UTF-8 왕복 변환을 확인한다."""
    text = unicodedata.normalize("NFC", str(value))
    return text.encode("utf-8").decode("utf-8")


@st.cache_resource(show_spinner=False)
def get_client():
    """secrets의 접속 정보로 Supabase 클라이언트를 만든다."""
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


def new_game():
    """후보 순서를 섞고 새 판을 시작한다."""
    candidates = [clean_text(m) for m in MENUS]
    random.shuffle(candidates)
    st.session_state.game_id = uuid.uuid4().hex
    st.session_state.current = candidates  # 이번 라운드 참가자
    st.session_state.winners = []  # 이번 라운드에서 이긴 반찬
    st.session_state.pair_idx = 0  # 이번 라운드의 몇 번째 대결인지
    st.session_state.duel_no = 0  # 지금까지 끝난 대결 수
    st.session_state.champion = None
    st.session_state.locked = False  # 저장 확인 실패 시 True


def save_duel(game_id: str, round_name: str, left: str, right: str, winner: str) -> bool:
    """서로 다른 두 후보 중 하나를 골랐을 때만 한 행을 저장하고, 저장 결과를 확인한다."""
    left, right, winner = clean_text(left), clean_text(right), clean_text(winner)
    if left == right or winner not in (left, right):
        return False

    row = {
        "game_id": clean_text(game_id),
        "round": clean_text(round_name),
        "left_menu": left,
        "right_menu": right,
        "winner": winner,
    }
    try:
        res = get_client().table(TABLE_NAME).insert(row).execute()
    except Exception:
        return False

    data = getattr(res, "data", None)
    if not data or len(data) != 1:
        return False
    saved = data[0]
    return (
        saved.get("game_id") == row["game_id"]
        and saved.get("round") == row["round"]
        and saved.get("left_menu") == left
        and saved.get("right_menu") == right
        and saved.get("winner") == winner
    )


def choose(side: str):
    """왼쪽/오른쪽 선택을 처리한다. 저장이 확인될 때만 다음 대결로 넘어간다."""
    ss = st.session_state
    if ss.locked or ss.champion is not None:
        return

    current = ss.current
    i = ss.pair_idx * 2
    if i + 1 >= len(current):
        return
    left, right = current[i], current[i + 1]
    winner = left if side == "left" else right
    round_name = ROUND_LABELS[len(current)]

    if not save_duel(ss.game_id, round_name, left, right, winner):
        ss.locked = True  # 재선택을 잠그고 진행하지 않는다.
        return

    ss.winners.append(winner)
    ss.pair_idx += 1
    ss.duel_no += 1

    if ss.pair_idx * 2 >= len(current):  # 이번 라운드 종료
        if len(current) == 2:
            ss.champion = winner
        else:
            ss.current = ss.winners
            ss.winners = []
            ss.pair_idx = 0


# ---------------------------------------------------------------------------
# 시작 준비
# ---------------------------------------------------------------------------
st.title("🍱 급식 월드컵")
st.caption("두 반찬 중 더 끌리는 쪽을 골라 주세요. 이름이나 학번은 필요하지 않아요.")

if "SUPABASE_URL" not in st.secrets or "SUPABASE_KEY" not in st.secrets:
    st.error("접속 정보(SUPABASE_URL, SUPABASE_KEY)를 secrets에서 찾을 수 없어요. 확인이 필요합니다.")
    st.stop()

if "game_id" not in st.session_state:
    new_game()

ss = st.session_state

# ---------------------------------------------------------------------------
# 화면
# ---------------------------------------------------------------------------
if ss.champion is not None:
    st.success("토너먼트가 끝났어요!")
    st.balloons()
    st.markdown("### 🏆 우승 반찬")
    st.markdown(f"# {ss.champion}")
    st.button("다시 시작", on_click=new_game, type="primary", key="restart_done")
else:
    current = ss.current
    round_name = ROUND_LABELS[len(current)]
    matches_in_round = len(current) // 2
    i = ss.pair_idx * 2
    left, right = current[i], current[i + 1]

    st.progress(ss.duel_no / TOTAL_DUELS, text=f"전체 {ss.duel_no + 1} / {TOTAL_DUELS}번째 선택")
    st.subheader(f"{round_name} · {ss.pair_idx + 1} / {matches_in_round}")

    if ss.locked:
        st.error(
            "이번 대결의 저장 결과를 확인하지 못했어요. "
            "대결을 더 진행하지 않고 선택을 잠갔습니다. 확인이 필요합니다."
        )

    col_left, col_right = st.columns(2)
    n = ss.duel_no
    with col_left:
        with st.container(border=True):
            st.markdown(f"<h3 style='text-align:center'>{left}</h3>", unsafe_allow_html=True)
            st.button(
                "이 반찬 선택",
                key=f"left_{n}",
                on_click=choose,
                args=("left",),
                disabled=ss.locked,
                use_container_width=True,
            )
    with col_right:
        with st.container(border=True):
            st.markdown(f"<h3 style='text-align:center'>{right}</h3>", unsafe_allow_html=True)
            st.button(
                "이 반찬 선택",
                key=f"right_{n}",
                on_click=choose,
                args=("right",),
                disabled=ss.locked,
                use_container_width=True,
            )

    st.divider()
    st.button("다시 시작", on_click=new_game, key="restart_mid")
import pandas as pd
import plotly.express as px

st.divider()
st.subheader("학급 대결 기록")

st.button("결과 새로 불러오기")
try:
    # 조회 시작 때의 마지막 id까지만, 빠짐없이 나누어 읽는다
    latest = db.table("menu_duels").select("id").order("id", desc=True).limit(1).execute().data
    upper = latest[0]["id"] if latest else 0
    records = []
    after = 0
    while after < upper:
        page = (db.table("menu_duels")
                .select("id,game_id,round,left_menu,right_menu,winner")
                .gt("id", after).lte("id", upper).order("id").limit(500).execute().data)
        if not page:
            raise RuntimeError("마지막 기록까지 조회하지 못했습니다.")
        records.extend(page)
        after = page[-1]["id"]
except Exception:
    st.error("기록을 불러오지 못했습니다.")
    st.stop()

if not records:
    st.info("아직 대결 기록이 없습니다.")
    st.stop()

duels = pd.DataFrame(records)
# 겨룬 횟수는 왼쪽과 오른쪽을 모두 센다
fought = pd.concat([duels["left_menu"], duels["right_menu"]]).value_counts()
won = duels["winner"].value_counts()
champion = duels[duels["round"] == "결승"]["winner"].value_counts()

board = pd.DataFrame({"겨룬 횟수": fought, "이긴 횟수": won, "우승": champion}).reindex(MENUS).fillna(0).astype(int)
board["승률(%)"] = (board["이긴 횟수"] / board["겨룬 횟수"].where(board["겨룬 횟수"] > 0) * 100).round(1)
board = board.sort_values("승률(%)", ascending=False).reset_index(names="반찬")

st.caption("대결 " + str(len(duels)) + "번 · 기록이 있는 판 " + str(duels["game_id"].nunique()) + "개")
st.caption("결승 기록이 있는 판 " + str(duels.loc[duels["round"] == "결승", "game_id"].nunique()) + "개 · 진행 중 기록도 포함합니다.")
st.caption("대결이 없는 후보의 승률은 비어 있습니다. 대결 수와 판 수는 참여 인원이 아닙니다.")
st.dataframe(board, hide_index=True, width="stretch")

fig = px.bar(board.dropna(subset=["승률(%)"]).sort_values("승률(%)"), x="승률(%)", y="반찬", orientation="h",
             text="승률(%)", color="승률(%)", color_continuous_scale="Oranges",
             title="반찬별 승률")
fig.update_layout(coloraxis_showscale=False, yaxis_title="")
st.plotly_chart(fig, width="stretch")
st.caption("조회 도중 들어온 새 기록은 다시 불러오면 반영됩니다. 승률은 대진표와 반복 참여의 영향을 받습니다.")
