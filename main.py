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
# -*- coding: utf-8 -*-
"""급식 월드컵 - 8강 토너먼트로 가장 맛있는 반찬을 뽑는 Streamlit 앱.

- 접속 정보: st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
- 저장 표: public.menu_duels (교사가 미리 만든 표에 그대로 연결, 새 표 생성 없음)
- 앱이 채우는 열: game_id, round, left_menu, right_menu, winner
  (id, created_at은 데이터베이스가 채움)
- 학급 분석 화면: menu_duels 전체 기록을 읽기만 한다(수정·삭제 기능 없음).
- 이름·학번·비밀번호는 받지 않음
"""

import random
import unicodedata
import uuid

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from supabase import create_client

TABLE_NAME = "menu_duels"  # public 스키마 표. 스키마 이름은 붙이지 않는다.
READ_COLUMNS = "id, game_id, round, left_menu, right_menu, winner"
PAGE_SIZE = 1000  # 한 번에 읽어 오는 행 수(전체 기록을 나눠서 모두 읽는다)

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
FINAL_ROUND = "결승"
TOTAL_DUELS = 7  # 8강 4번 + 4강 2번 + 결승 1번

VIEW_GAME = "🍱 게임"
VIEW_STATS = "📊 학급 분석"

st.set_page_config(page_title="급식 월드컵", page_icon="🍱", layout="centered")


# ---------------------------------------------------------------------------
# 유틸리티
# ---------------------------------------------------------------------------
def clean_text(value) -> str:
    """한글이 깨지지 않도록 NFC로 정규화하고 UTF-8 왕복 변환을 확인한다."""
    if value is None:
        return ""
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

    ss.analysis_dirty = True  # 새 기록이 생겼으니 분석 화면은 다시 불러온다.
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
# 학급 분석: 읽기 전용
# ---------------------------------------------------------------------------
def fetch_all_duels() -> list:
    """menu_duels의 전체 기록을 여섯 열만 골라 모두 읽어 온다."""
    client = get_client()
    rows = []
    start = 0
    while True:
        res = (
            client.table(TABLE_NAME)
            .select(READ_COLUMNS)
            .order("id")
            .range(start, start + PAGE_SIZE - 1)
            .execute()
        )
        data = getattr(res, "data", None) or []
        rows.extend(data)
        if len(data) < PAGE_SIZE:
            break
        start += PAGE_SIZE
    return rows


def load_analysis():
    """기록을 불러와 세션에 담는다. 실패하면 rows를 None으로 두어 '빈 기록'과 구분한다."""
    ss = st.session_state
    try:
        ss.analysis_rows = fetch_all_duels()
        ss.analysis_error = False
    except Exception:
        ss.analysis_rows = None
        ss.analysis_error = True
    ss.analysis_dirty = False


def compute_stats(rows: list) -> list:
    """후보마다 대결 수·승리 수·승률·우승 횟수를 센다."""
    duels = {m: 0 for m in MENUS}
    wins = {m: 0 for m in MENUS}
    titles = {m: 0 for m in MENUS}

    for row in rows:
        left = clean_text(row.get("left_menu"))
        right = clean_text(row.get("right_menu"))
        winner = clean_text(row.get("winner"))
        round_name = clean_text(row.get("round"))

        for menu in {left, right}:  # 양쪽을 모두 센다.
            if menu in duels:
                duels[menu] += 1
        if winner in wins:
            wins[winner] += 1
            if round_name == FINAL_ROUND:
                titles[winner] += 1

    stats = []
    for m in MENUS:
        rate = (wins[m] / duels[m] * 100) if duels[m] > 0 else None
        stats.append(
            {"menu": m, "duels": duels[m], "wins": wins[m], "rate": rate, "titles": titles[m]}
        )

    stats.sort(
        key=lambda s: (
            s["rate"] is None,  # 승률을 알 수 없는 후보는 맨 뒤
            -(s["rate"] if s["rate"] is not None else 0),
            -s["wins"],
            -s["duels"],
            s["menu"],
        )
    )
    return stats


def render_stats():
    ss = st.session_state
    st.subheader("학급 전체 대결 분석")

    reload_clicked = st.button("결과 다시 불러오기", key="reload_stats")
    if reload_clicked or "analysis_rows" not in ss or ss.get("analysis_dirty", True):
        with st.spinner("대결 기록을 불러오는 중이에요..."):
            load_analysis()

    if ss.analysis_error or ss.analysis_rows is None:
        st.error(
            "대결 기록을 불러오지 못했어요. 그래서 분석을 보여 줄 수 없어요. "
            "잠시 뒤 '결과 다시 불러오기'를 눌러 주세요. 계속되면 확인이 필요합니다."
        )
        return

    rows = ss.analysis_rows
    if len(rows) == 0:
        st.info("아직 저장된 대결 기록이 없어요. 게임을 한 판 진행하면 이곳에 분석이 나타나요.")
        return

    game_count = len({clean_text(r.get("game_id")) for r in rows})
    st.markdown(f"**집계에 사용한 대결 기록 {len(rows):,}건 · {game_count:,}판**")
    st.caption(
        "기록 수는 참여 인원과 달라요. 한 사람이 여러 판을 할 수 있고, "
        "끝까지 가지 않고 중간에 멈춘 판의 대결도 집계에 들어가요. "
        "우승 횟수는 '결승' 기록의 승자를 센 값이에요."
    )

    stats = compute_stats(rows)

    # 표(승률 높은 순)
    table = pd.DataFrame(
        {
            "반찬": [s["menu"] for s in stats],
            "대결 수": [s["duels"] for s in stats],
            "승리 수": [s["wins"] for s in stats],
            "승률": [
                f"{s['rate']:.1f}%" if s["rate"] is not None else "아직 알 수 없음"
                for s in stats
            ],
            "우승 횟수": [s["titles"] for s in stats],
        }
    )
    st.dataframe(table, hide_index=True, width="stretch")

    no_record = [s["menu"] for s in stats if s["rate"] is None]
    if no_record:
        st.caption(
            "대결 기록이 없는 후보는 승률을 아직 알 수 없어요: " + ", ".join(no_record)
        )

    # 가로 막대그래프(plotly)
    order = [s["menu"] for s in stats]
    known = [s for s in stats if s["rate"] is not None]
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=[s["menu"] for s in known],
            x=[s["rate"] for s in known],
            orientation="h",
            text=[f"{s['rate']:.1f}%" for s in known],
            textposition="outside",
            customdata=[[s["duels"], s["wins"], s["titles"]] for s in known],
            hovertemplate=(
                "<b>%{y}</b><br>승률 %{x:.1f}%<br>대결 수 %{customdata[0]}"
                "<br>승리 수 %{customdata[1]}<br>우승 횟수 %{customdata[2]}<extra></extra>"
            ),
        )
    )
    for menu in no_record:  # 0%로 오해하지 않도록 막대 대신 안내 문구를 둔다.
        fig.add_annotation(
            x=0, y=menu, text="아직 알 수 없음", showarrow=False, xanchor="left"
        )
    fig.update_layout(
        title="반찬별 승률",
        height=420,
        margin=dict(l=10, r=40, t=50, b=10),
        showlegend=False,
        xaxis=dict(title="승률(%)", range=[0, 110], ticksuffix="%"),
        yaxis=dict(
            categoryorder="array",
            categoryarray=order,
            autorange="reversed",  # 승률이 높은 후보가 위쪽
        ),
    )
    st.plotly_chart(fig, width="stretch")


# ---------------------------------------------------------------------------
# 게임 화면
# ---------------------------------------------------------------------------
def render_game():
    ss = st.session_state

    if ss.champion is not None:
        st.success("토너먼트가 끝났어요!")
        st.balloons()
        st.markdown("### 🏆 우승 반찬")
        st.markdown(f"# {ss.champion}")
        st.caption("위의 '학급 분석'에서 우리 반 전체 기록도 볼 수 있어요.")
        st.button("다시 시작", on_click=new_game, type="primary", key="restart_done")
        return

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
                width="stretch",
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
                width="stretch",
            )

    st.divider()
    st.button("다시 시작", on_click=new_game, key="restart_mid")


# ---------------------------------------------------------------------------
# 시작 준비와 화면 전환
# ---------------------------------------------------------------------------
st.title("🍱 급식 월드컵")
st.caption("두 반찬 중 더 끌리는 쪽을 골라 주세요. 이름이나 학번은 필요하지 않아요.")

if "SUPABASE_URL" not in st.secrets or "SUPABASE_KEY" not in st.secrets:
    st.error("접속 정보(SUPABASE_URL, SUPABASE_KEY)를 secrets에서 찾을 수 없어요. 확인이 필요합니다.")
    st.stop()

if "game_id" not in st.session_state:
    new_game()

view = st.radio(
    "화면",
    [VIEW_GAME, VIEW_STATS],
    horizontal=True,
    key="view",
    label_visibility="collapsed",
)

if view == VIEW_STATS:
    render_stats()
else:
    render_game()
