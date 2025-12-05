import pandas as pd
import streamlit as st
from supabase import create_client, Client

# -------------------------------------------------
#  CONFIG – SUPABASE
# -------------------------------------------------

@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


supabase = get_supabase()

ADMIN_EMAIL = st.secrets["ADMIN_EMAIL"]
ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]

# Residential circle & construction rates (for colony preview)
CIRCLE_RATES_RES = {
    "A": 774000,
    "B": 245520,
    "C": 159840,
    "D": 127680,
    "E": 70080,
    "F": 56640,
    "G": 46200,
    "H": 23280,
}
CONSTRUCTION_RATES_RES = {
    "A": 21960,
    "B": 17400,
    "C": 13920,
    "D": 11160,
    "E": 9360,
    "F": 8220,
    "G": 6960,
    "H": 3480,
}

# -------------------------------------------------
#  SESSION STATE
# -------------------------------------------------

def ensure_state():
    if "admin_auth" not in st.session_state:
        st.session_state.admin_auth = False


ensure_state()

# -------------------------------------------------
#  PAGE CONFIG & THEME
# -------------------------------------------------

st.set_page_config(
    page_title="Admin Dashboard – Delhi Property Calculator",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        .stApp {
            background: radial-gradient(circle at top, #1f2933 0, #020617 55%, #000000 100%);
            color: #E5E7EB;
        }
        /* Main Title */
        .main-title {
            font-size: 32px;
            font-weight: 900;
            letter-spacing: 0.03em;
            color: #38bdf8;
            margin-bottom: 4px;
        }
        .sub-title {
            font-size: 14px;
            color: #9CA3AF;
            margin-bottom: 16px;
        }
        .metric-box {
            background: linear-gradient(135deg, rgba(15,23,42,0.9), rgba(30,64,175,0.52));
            border-radius: 16px;
            padding: 18px 20px;
            box-shadow: 0 18px 40px rgba(0,0,0,0.45);
            border: 1px solid rgba(148,163,184,0.45);
        }
        .big-number {
            font-size: 24px;
            font-weight: 800;
            color: #E5E7EB;
        }
        .metric-label {
            font-size: 13px;
            color: #9CA3AF;
            margin-top: 4px;
        }
        .glass-card {
            background: rgba(15,23,42,0.72);
            border-radius: 18px;
            padding: 22px 20px;
            border: 1px solid rgba(148,163,184,0.4);
            box-shadow: 0 18px 45px rgba(0,0,0,0.6);
        }
        .login-title {
            font-size: 20px;
            font-weight: 700;
            color: #E5E7EB;
            margin-bottom: 4px;
        }
        .login-sub {
            font-size: 12px;
            color: #9CA3AF;
            margin-bottom: 12px;
        }
        [data-testid="stSidebar"] {
            background: radial-gradient(circle at top left, #0b1120, #020617);
            border-right: 1px solid rgba(148,163,184,0.35);
        }
        .lock-screen {
            text-align: center;
            margin-top: 80px;
        }
        .lock-icon {
            font-size: 40px;
            margin-bottom: 10px;
        }
        .lock-title {
            font-size: 22px;
            font-weight: 700;
            color: #E5E7EB;
        }
        .lock-text {
            font-size: 14px;
            color: #9CA3AF;
            max-width: 480px;
            margin: 8px auto 0 auto;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------------------------------
#  SIDEBAR – ADMIN LOGIN
# -------------------------------------------------

with st.sidebar:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<div class="login-title">🛡️ Admin Access</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="login-sub">Restricted dashboard for Aggarwal Documents & Legal Consultants.</div>',
        unsafe_allow_html=True,
    )

    if not st.session_state.admin_auth:
        email = st.text_input("Admin Email", value="", placeholder="Enter admin email")
        pw = st.text_input("Admin Password", type="password", placeholder="Enter admin password")

        if st.button("Login as Admin", use_container_width=True):
            if email == ADMIN_EMAIL and pw == ADMIN_PASSWORD:
                st.session_state.admin_auth = True
                st.success("Admin login successful.")
                st.experimental_rerun()
            else:
                st.error("Invalid admin credentials.")
    else:
        st.success(f"Logged in as: {ADMIN_EMAIL}")
        if st.button("Logout", use_container_width=True):
            st.session_state.admin_auth = False
            st.experimental_rerun()

    st.markdown("</div>", unsafe_allow_html=True)

# If not logged in – show lock screen in main area and stop
if not st.session_state.admin_auth:
    st.markdown(
        """
        <div class="lock-screen">
            <div class="lock-icon">🔒</div>
            <div class="lock-title">Admin Dashboard Locked</div>
            <div class="lock-text">
                Please login with valid admin credentials from the left sidebar
                to view user data, history, colonies and tracking events.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

# -------------------------------------------------
#  HELPER – LOAD TABLE
# -------------------------------------------------

def load_table(name: str, select: str = "*") -> pd.DataFrame:
    """
    Generic loader. If table missing or error, returns empty DataFrame
    and shows a friendly message.
    """
    try:
        res = supabase.table(name).select(select).execute()
        rows = res.data or []
        return pd.DataFrame(rows)
    except Exception as e:
        st.warning(f"Could not load table '{name}': {e}")
        return pd.DataFrame()

# -------------------------------------------------
#  HEADER
# -------------------------------------------------

st.markdown(
    '<div class="main-title">Admin Dashboard</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="sub-title">Internal monitoring panel for Delhi Property Price Calculator</div>',
    unsafe_allow_html=True,
)
st.write("---")

# -------------------------------------------------
#  TABS
# -------------------------------------------------

tab_overview, tab_users, tab_colonies, tab_history, tab_otps, tab_events = st.tabs(
    ["📊 Overview", "👥 Users", "📌 Colonies", "📂 History", "🔑 OTP Logs", "📁 Events"]
)

# -------------------------------------------------
#  OVERVIEW TAB
# -------------------------------------------------

with tab_overview:
    users_df = load_table("users", "id, email, created_at, last_login")
    history_df = load_table("history")
    events_df = load_table("events")
    otps_df = load_table("otps")

    total_users = len(users_df)
    total_history = len(history_df)
    total_events = len(events_df)
    total_otps = len(otps_df)

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(
            f"""
            <div class="metric-box">
                <div class="big-number">{total_users}</div>
                <div class="metric-label">Total Users</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown(
            f"""
            <div class="metric-box">
                <div class="big-number">{total_history}</div>
                <div class="metric-label">Saved Calculations</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c3:
        st.markdown(
            f"""
            <div class="metric-box">
                <div class="big-number">{total_otps}</div>
                <div class="metric-label">OTP Records</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c4:
        st.markdown(
            f"""
            <div class="metric-box">
                <div class="big-number">{total_events}</div>
                <div class="metric-label">Tracked Events</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.write("### 👤 Latest Registered Users")
    if not users_df.empty:
        try:
            users_df_sorted = users_df.sort_values("created_at", ascending=False)
        except Exception:
            users_df_sorted = users_df
        st.dataframe(users_df_sorted.head(20), use_container_width=True)
    else:
        st.info("No users found yet.")

# -------------------------------------------------
#  USERS TAB
# -------------------------------------------------

with tab_users:
    st.subheader("👥 All Users")

    df = load_table("users")
    if df.empty:
        st.info("No users in the database.")
    else:
        search = st.text_input("Search user by email")
        if search:
            df = df[df["email"].str.contains(search, case=False, na=False)]
        st.dataframe(df, use_container_width=True)

# -------------------------------------------------
#  COLONIES TAB  (with auto land & construction rates)
# -------------------------------------------------

with tab_colonies:
    st.subheader("📌 Colonies & Circle Rates (Residential)")

    col_df = load_table("colonies")

    if col_df.empty:
        st.info("No colonies found in the 'colonies' table.")
    else:
        # Normalise column names just in case
        col_df.columns = [c.strip() for c in col_df.columns]

        # Derive land & construction rates based on category (residential)
        if "category" in col_df.columns:
            col_df["category"] = col_df["category"].astype(str).str.upper()
            col_df["land_rate"] = col_df["category"].map(CIRCLE_RATES_RES).fillna(0)
            col_df["construction_rate"] = col_df["category"].map(CONSTRUCTION_RATES_RES).fillna(0)
        else:
            col_df["land_rate"] = 0
            col_df["construction_rate"] = 0

        if "colony_name" in col_df.columns:
            search = st.text_input("Search colony by name")
            if search:
                col_df = col_df[col_df["colony_name"].str.contains(search, case=False, na=False)]

        # Re-order columns nicely if possible
        display_cols = []
        for c in ["id", "colony_name", "category", "land_rate", "construction_rate"]:
            if c in col_df.columns:
                display_cols.append(c)
        for c in col_df.columns:
            if c not in display_cols:
                display_cols.append(c)

        st.dataframe(col_df[display_cols], use_container_width=True)

        # Optional export
        csv = col_df[display_cols].to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download Colonies as CSV",
            data=csv,
            file_name="colonies_with_rates.csv",
            mime="text/csv",
        )

# -------------------------------------------------
#  HISTORY TAB
# -------------------------------------------------

with tab_history:
    st.subheader("📂 Calculation History")

    hist_df = load_table("history")
    if hist_df.empty:
        st.info("No calculation history yet.")
    else:
        users_df = load_table("users", "id, email")
        if not users_df.empty and "id" in users_df.columns:
            id_to_email = dict(zip(users_df["id"], users_df["email"]))
            hist_df["user_email"] = hist_df["user_id"].map(id_to_email)

        cols = [
            "created_at",
            "user_email",
            "user_id",
            "colony_name",
            "property_type",
            "category",
            "consideration",
            "stamp_duty",
            "e_fees",
            "tds",
            "total_govt_duty",
        ]
        # Keep only existing columns
        cols = [c for c in cols if c in hist_df.columns]
        try:
            hist_df_sorted = hist_df.sort_values("created_at", ascending=False)
        except Exception:
            hist_df_sorted = hist_df

        st.dataframe(hist_df_sorted[cols], use_container_width=True)

# -------------------------------------------------
#  OTP LOGS TAB
# -------------------------------------------------

with tab_otps:
    st.subheader("🔑 OTP Logs")

    otp_df = load_table("otps")
    if otp_df.empty:
        st.info("No OTP logs yet.")
    else:
        try:
            otp_df_sorted = otp_df.sort_values("created_at", ascending=False)
        except Exception:
            otp_df_sorted = otp_df
        st.dataframe(otp_df_sorted, use_container_width=True)

# -------------------------------------------------
#  EVENTS TAB
# -------------------------------------------------

with tab_events:
    st.subheader("📁 Event Logs (Visits, Logins, Calculations)")

    ev_df = load_table("events")
    if ev_df.empty:
        st.info("No events tracked yet.")
    else:
        try:
            ev_df_sorted = ev_df.sort_values("created_at", ascending=False)
        except Exception:
            ev_df_sorted = ev_df

        search_ev = st.text_input("Search by email or event type")
        if search_ev:
            mask = (
                ev_df_sorted["email"].astype(str).str.contains(search_ev, case=False, na=False)
                | ev_df_sorted["event_type"].astype(str).str.contains(search_ev, case=False, na=False)
            )
            ev_df_sorted = ev_df_sorted[mask]

        st.dataframe(ev_df_sorted, use_container_width=True)
