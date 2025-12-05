import pandas as pd
import streamlit as st
from supabase import create_client, Client

# -------------------------------------------------
# CONFIG
# -------------------------------------------------

@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_supabase()

ADMIN_EMAIL = st.secrets["ADMIN_EMAIL"]
ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]


# -------------------------------------------------
# SESSION STATE
# -------------------------------------------------

def ensure_state():
    if "admin_auth" not in st.session_state:
        st.session_state.admin_auth = False

ensure_state()


# -------------------------------------------------
# PAGE UI THEME
# -------------------------------------------------

st.set_page_config(
    page_title="Admin Dashboard – Delhi Property Calculator",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
    <style>
        .stApp {
            background: linear-gradient(135deg, #0E1117, #1A1D24);
            color: #E4E4E4;
        }
        .main-title {
            font-size: 32px;
            font-weight: 900;
            color: #4BC0FF;
            padding-bottom: 10px;
        }
        .sub-title {
            font-size: 15px;
            color: #9EB4C7;
        }
        .metric-box {
            background: rgba(255,255,255,0.05);
            padding: 18px;
            border-radius: 12px;
            text-align: center;
        }
        .big-number {
            font-size: 24px;
            font-weight: 700;
            color: #4BC0FF;
        }
        .label {
            font-size: 14px;
            color: #C8D5E0;
        }
    </style>
""", unsafe_allow_html=True)


# -------------------------------------------------
# SIDEBAR ADMIN LOGIN
# -------------------------------------------------

with st.sidebar:
    st.header("🔐 Admin Login")

    if not st.session_state.admin_auth:
        email = st.text_input("Admin Email")
        pw = st.text_input("Admin Password", type="password")

        if st.button("Login", use_container_width=True):
            if email == ADMIN_EMAIL and pw == ADMIN_PASSWORD:
                st.session_state.admin_auth = True
                st.success("Login successful.")
                st.rerun()
            else:
                st.error("Invalid admin credentials.")
    else:
        st.success(f"Logged in as: {ADMIN_EMAIL}")
        if st.button("Logout", use_container_width=True):
            st.session_state.admin_auth = False
            st.rerun()

if not st.session_state.admin_auth:
    st.stop()


# -------------------------------------------------
# HELPER – LOAD TABLE
# -------------------------------------------------

def load_table(name: str, select="*"):
    try:
        res = supabase.table(name).select(select).execute()
        rows = res.data or []
        return pd.DataFrame(rows)
    except Exception as e:
        st.error(f"Error loading table '{name}': {e}")
        return pd.DataFrame()


# -------------------------------------------------
# HEADER
# -------------------------------------------------

st.markdown('<p class="main-title">🛡️ Admin Dashboard</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Internal dashboard for Delhi Property Price Calculator</p>',
            unsafe_allow_html=True)
st.write("---")


# -------------------------------------------------
# TABS
# -------------------------------------------------

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    ["📊 Overview", "👥 Users", "📌 Colonies", "📂 History", "🔑 OTP Logs", "📁 Events"]
)


# -------------------------------------------------
# OVERVIEW TAB
# -------------------------------------------------

with tab1:
    users_df = load_table("users", "id, email, created_at, last_login")
    history_df = load_table("history")
    events_df = load_table("events")
    otps_df = load_table("otps")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        <div class="metric-box">
            <div class="big-number">{len(users_df)}</div>
            <div class="label">Total Users</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="metric-box">
            <div class="big-number">{len(history_df)}</div>
            <div class="label">Saved Calculations</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="metric-box">
            <div class="big-number">{len(otps_df)}</div>
            <div class="label">OTP Records</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
        <div class="metric-box">
            <div class="big-number">{len(events_df)}</div>
            <div class="label">Event Logs</div>
        </div>
        """, unsafe_allow_html=True)

    st.write("### 👤 Latest Registered Users")

    if not users_df.empty:
        st.dataframe(users_df.sort_values("created_at", ascending=False).head(15),
                     use_container_width=True)


# -------------------------------------------------
# USERS TAB
# -------------------------------------------------

with tab2:
    st.subheader("👥 All Users")
    df = load_table("users")
    if not df.empty:
        search = st.text_input("Search user by email")
        if search:
            df = df[df["email"].str.contains(search, case=False)]
        st.dataframe(df, use_container_width=True)


# -------------------------------------------------
# COLONIES TAB
# -------------------------------------------------

with tab3:
    st.subheader("📌 Colony List")
    df = load_table("colonies", "id, colony_name, category")
    if not df.empty:
        search = st.text_input("Search colony")
        if search:
            df = df[df["colony_name"].str.contains(search, case=False)]
        st.dataframe(df, use_container_width=True)


# -------------------------------------------------
# HISTORY TAB (FIXED)
# -------------------------------------------------

with tab4:
    st.subheader("📂 Calculation History")

    hist_df = load_table("history")
    if not hist_df.empty:

        users_df = load_table("users", "id, email")
        id_to_email = dict(zip(users_df["id"], users_df["email"]))
        hist_df["user_email"] = hist_df["user_id"].map(id_to_email)

        cols = [
            "created_at",
            "user_email",
            "colony_name",
            "property_type",
            "category",
            "consideration",
            "stamp_duty",
            "e_fees",
            "tds",
            "total_govt_duty",
        ]

        cols = [c for c in cols if c in hist_df.columns]
        hist_df = hist_df[cols]

        st.dataframe(hist_df.sort_values("created_at", ascending=False),
                     use_container_width=True)


# -------------------------------------------------
# OTP LOGS TAB
# -------------------------------------------------

with tab5:
    st.subheader("🔑 OTP Logs")
    df = load_table("otps")
    if not df.empty:
        st.dataframe(df.sort_values("created_at", ascending=False),
                     use_container_width=True)


# -------------------------------------------------
# EVENTS TAB
# -------------------------------------------------

with tab6:
    st.subheader("📁 Events Logs")
    df = load_table("events")
    if not df.empty:
        st.dataframe(df.sort_values("created_at", ascending=False),
                     use_container_width=True)
