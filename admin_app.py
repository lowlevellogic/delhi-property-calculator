import pandas as pd
import streamlit as st
from supabase import create_client, Client

# -------------------------------------------------
# SUPABASE & ADMIN AUTH
# -------------------------------------------------


@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


supabase = get_supabase()

ADMIN_EMAIL = st.secrets["ADMIN_EMAIL"]
ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]


def ensure_state():
    if "admin_auth" not in st.session_state:
        st.session_state.admin_auth = False


ensure_state()

st.set_page_config(page_title="Admin – Delhi Property Calculator", layout="wide")

st.title("🛡️ Admin Dashboard")
st.caption("Internal dashboard – Aggarwal Documents & Legal Consultants")

# ---------- LOGIN ----------
with st.sidebar:
    st.header("Admin Login")

    if not st.session_state.admin_auth:
        email = st.text_input("Admin Email")
        pw = st.text_input("Admin Password", type="password")
        if st.button("Login as Admin"):
            if email == ADMIN_EMAIL and pw == ADMIN_PASSWORD:
                st.session_state.admin_auth = True
                st.success("Admin login successful.")
                st.rerun()
            else:
                st.error("Invalid admin credentials.")
    else:
        st.success(f"Logged in as admin: {ADMIN_EMAIL}")
        if st.button("Logout"):
            st.session_state.admin_auth = False
            st.rerun()

if not st.session_state.admin_auth:
    st.stop()

# -------------------------------------------------
# HELPER TO LOAD TABLES
# -------------------------------------------------


def load_table(name: str, select: str = "*"):
    try:
        res = supabase.table(name).select(select).execute()
        data = res.data or []
        if not data:
            st.info(f"No rows in table '{name}'.")
            return pd.DataFrame()
        return pd.DataFrame(data)
    except Exception as e:
        st.warning(f"Could not load table '{name}': {e}")
        return pd.DataFrame()


tab_overview, tab_users, tab_colonies, tab_history, tab_otps, tab_events = st.tabs(
    ["Overview", "Users", "Colonies", "History", "OTP Logs", "Events"]
)

# ---------- OVERVIEW ----------
with tab_overview:
    st.subheader("Overview")

    users_df = load_table(
        "users", "id, email, created_at, last_login, city, device"
    )
    hist_df = load_table("history")
    events_df = load_table("events")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Users", len(users_df))
    with col2:
        st.metric("Saved Calculations", len(hist_df))
    with col3:
        st.metric("Tracked Events", len(events_df))

    st.write("### Recent Users")
    if not users_df.empty:
        st.dataframe(
            users_df.sort_values("created_at", ascending=False).head(20),
            use_container_width=True,
        )

# ---------- USERS ----------
with tab_users:
    st.subheader("Users")
    users_df = load_table(
        "users", "id, email, created_at, last_login, city, device"
    )
    if not users_df.empty:
        search = st.text_input("Search email")
        if search:
            users_df = users_df[users_df["email"].str.contains(search, case=False)]
        st.dataframe(users_df, use_container_width=True)

# ---------- COLONIES ----------
with tab_colonies:
    st.subheader("Colonies")
    col_df = load_table("colonies", "id, colony_name, category")
    if not col_df.empty:
        search = st.text_input("Search colony")
        if search:
            col_df = col_df[col_df["colony_name"].str.contains(search, case=False)]
        st.dataframe(col_df, use_container_width=True)

# ---------- HISTORY ----------
with tab_history:
    st.subheader("Calculation History")
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
        st.dataframe(hist_df.sort_values("created_at", ascending=False), use_container_width=True)

# ---------- OTP LOGS ----------
with tab_otps:
    st.subheader("OTP Logs")
    otps_df = load_table(
        "otps", "id, email, purpose, otp_code, used, expires_at, created_at"
    )
    if not otps_df.empty:
        st.dataframe(
            otps_df.sort_values("created_at", ascending=False),
            use_container_width=True,
        )

# ---------- EVENTS ----------
with tab_events:
    st.subheader("Event Logs")
    events_df = load_table("events")
    if not events_df.empty:
        st.dataframe(
            events_df.sort_values("created_at", ascending=False),
            use_container_width=True,
        )

