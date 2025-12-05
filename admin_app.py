# admin_app.py

import pandas as pd
import streamlit as st
from datetime import datetime, date
from supabase import create_client, Client

# -------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------

st.set_page_config(
    page_title="Admin Dashboard – Delhi Property Calculator",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -------------------------------------------------
# GLOBAL CSS – PREMIUM GLASS LOGIN + DARK ADMIN UI
# -------------------------------------------------

st.markdown(""" 
<style>

.stApp {
    background: radial-gradient(circle at top left, #1f2933 0%, #020617 60%);
    color: #e5e7eb;
}

/* -------- PREMIUM LOGIN CARD -------- */
.login-card {
    width: 480px;
    padding: 40px 32px 32px 32px;
    border-radius: 28px;
    margin-left: auto;
    margin-right: auto;
    background: rgba(17, 25, 40, 0.72);
    backdrop-filter: blur(22px) saturate(180%);
    border: 1px solid rgba(255, 255, 255, 0.18);
    box-shadow: 0 20px 60px rgba(0,0,0,0.55);
}

.login-title {
    font-size: 26px;
    font-weight: 900;
    color: white;
    text-align: center;
}

.login-subtitle {
    font-size: 14px;
    color: #a9b2c9;
    text-align: center;
    margin-bottom: 20px;
}

.login-badge {
    font-size: 12px;
    color: #38bdf8;
    font-weight: 600;
    text-align: center;
    letter-spacing: 0.10em;
    margin-bottom: 6px;
    text-transform: uppercase;
}

.metric-box {
    background: rgba(15, 23, 42, 0.85);
    padding: 18px;
    border-radius: 16px;
    text-align: center;
    border: 1px solid rgba(148, 163, 184, 0.3);
}

.big-number {
    font-size: 24px;
    font-weight: 700;
    color: #38bdf8;
}

.label {
    font-size: 13px;
    color: #cbd5f5;
}

.danger-text {
    color: #f97373;
    font-size: 13px;
}

</style>
""", unsafe_allow_html=True)

# -------------------------------------------------
# SUPABASE CLIENT
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
# HELPER – LOAD TABLE
# -------------------------------------------------

def load_table(name: str, select="*"):
    try:
        res = supabase.table(name).select(select).execute()
        return pd.DataFrame(res.data or [])
    except Exception as e:
        st.error(f"Error loading table {name}: {e}")
        return pd.DataFrame()

# -------------------------------------------------
# LOGIN PAGE (PREMIUM)
# -------------------------------------------------

def render_login():
    st.markdown("<br><br><br>", unsafe_allow_html=True)

    with st.container():
        st.image("logo.jpg", width=130)

        st.markdown('<div class="login-card">', unsafe_allow_html=True)

        st.markdown("""
            <div class="login-badge">Aggarwal Documents & Legal Consultants</div>
            <div class="login-title">Admin Control Panel</div>
            <div class="login-subtitle">
                Secure access to users, history, colony master & events.
            </div>
        """, unsafe_allow_html=True)

        email = st.text_input("Admin Email", key="admin_email_login")
        pw = st.text_input("Admin Password", type="password", key="admin_pw_login")

        if st.button("Login as Admin", use_container_width=True):
            if email == ADMIN_EMAIL and pw == ADMIN_PASSWORD:
                st.session_state.admin_auth = True
                st.rerun()
            else:
                st.error("Invalid admin credentials")

        st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------------------------
# CHECK LOGIN STATUS
# -------------------------------------------------

if "admin_auth" not in st.session_state:
    st.session_state.admin_auth = False

if not st.session_state.admin_auth:
    with st.sidebar:
        st.markdown("### Admin Login Required")
    render_login()
    st.stop()

# -------------------------------------------------
# SIDEBAR (AFTER LOGIN)
# -------------------------------------------------

with st.sidebar:
    st.markdown("### 🛡️ Admin")
    st.caption(f"Logged in as **{ADMIN_EMAIL}**")

    if st.button("Logout", use_container_width=True):
        st.session_state.admin_auth = False
        st.rerun()

# -------------------------------------------------
# HEADER
# -------------------------------------------------

st.markdown("<h1 style='color:#38bdf8;'>🛡️ Admin Dashboard</h1>", unsafe_allow_html=True)
st.write("---")

# -------------------------------------------------
# TABS
# -------------------------------------------------

tab_overview, tab_users, tab_colonies, tab_history, tab_otps, tab_events = st.tabs([
    "📊 Overview", "👥 Users", "📌 Colonies",
    "📂 History", "🔑 OTP Logs", "📁 Events"
])

# -------------------------------------------------
# OVERVIEW TAB
# -------------------------------------------------

with tab_overview:
    users_df = load_table("users")
    hist_df = load_table("history")
    otp_df = load_table("otps")
    ev_df = load_table("events")

    c1, c2, c3, c4 = st.columns(4)

    c1.markdown(f"<div class='metric-box'><div class='big-number'>{len(users_df)}</div><div class='label'>Users</div></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='metric-box'><div class='big-number'>{len(hist_df)}</div><div class='label'>History</div></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='metric-box'><div class='big-number'>{len(otp_df)}</div><div class='label'>OTP Logs</div></div>", unsafe_allow_html=True)
    c4.markdown(f"<div class='metric-box'><div class='big-number'>{len(ev_df)}</div><div class='label'>Events</div></div>", unsafe_allow_html=True)

    st.write("### Latest Users")
    if not users_df.empty:
        st.dataframe(users_df.sort_values("created_at", ascending=False).head(10), use_container_width=True)

# -------------------------------------------------
# USERS TAB
# -------------------------------------------------

with tab_users:
    st.subheader("All Users")
    df = load_table("users")
    if df.empty:
        st.info("No users found.")
    else:
        search = st.text_input("Search email")
        if search:
            df = df[df["email"].str.contains(search, case=False)]

        st.dataframe(df, use_container_width=True)

        st.write("---")
        st.subheader("User Details & History")

        user_list = ["Select user"] + sorted(df["email"].unique().tolist())
        selected = st.selectbox("Choose user", user_list)

        if selected != "Select user":
            user_row = df[df["email"] == selected].iloc[0]
            user_id = user_row["id"]

            st.metric("Email", selected)
            st.metric("Created", user_row.get("created_at", "-"))
            st.metric("Last Login", user_row.get("last_login", "-"))

            hist = load_table("history")
            hist = hist[hist["user_id"] == user_id]

            st.write("### User's Calculation History")
            st.dataframe(hist, use_container_width=True)

            if st.button("Clear User History"):
                supabase.table("history").delete().eq("user_id", user_id).execute()
                st.success("History cleared")
                st.rerun()

            if st.button("Delete User Completely"):
                supabase.table("users").delete().eq("id", user_id).execute()
                st.success("User deleted")
                st.rerun()

# -------------------------------------------------
# COLONY MASTER TAB (FULL CONTROL)
# -------------------------------------------------

with tab_colonies:
    st.subheader("🏙 Colony Master (Add / Edit / Delete)")
    st.caption("Manage colonies & update land / construction rates.")

    df = load_table("colonies")

    # ------------------------
    # SEARCH
    # ------------------------
    st.write("### 🔍 Search Colonies")
    q = st.text_input("Search colony name...")
    if q:
        df_show = df[df["colony_name"].str.contains(q, case=False, na=False)]
    else:
        df_show = df

    st.dataframe(df_show, use_container_width=True)

    st.write("---")

    # ------------------------
    # ADD NEW COLONY
    # ------------------------
    st.write("### ➕ Add New Colony")
    c1, c2 = st.columns(2)

    with c1:
        new_colony = st.text_input("Colony Name", key="new_colony_name")
    with c2:
        new_category = st.selectbox("Category", list("ABCDEFGH"), key="new_colony_category")

    if st.button("Add Colony"):
        if not new_colony:
            st.error("Enter colony name.")
        else:
            supabase.table("colonies").insert({
                "colony_name": new_colony,
                "category": new_category,
                "res_land_rate": None,
                "res_const_rate": None,
                "com_land_rate": None,
                "com_const_rate": None,
            }).execute()
            st.success("Colony added successfully.")
            st.rerun()

    st.write("---")

    # ------------------------
    # EDIT RATES
    # ------------------------
    st.write("### ✏ Update Colony Rates")

    colony_list = df["colony_name"].tolist()
    selected = st.selectbox("Select colony", ["Select colony"] + colony_list)

    if selected != "Select colony":
        sel = df[df["colony_name"] == selected].iloc[0]

        r1, r2 = st.columns(2)
        r3, r4 = st.columns(2)

        with r1:
            new_rl = st.number_input("Residential Land Rate", value=sel.get("res_land_rate") or 0, step=100)
        with r2:
            new_rc = st.number_input("Residential Construction Rate", value=sel.get("res_const_rate") or 0, step=100)
        with r3:
            new_cl = st.number_input("Commercial Land Rate", value=sel.get("com_land_rate") or 0, step=100)
        with r4:
            new_cc = st.number_input("Commercial Construction Rate", value=sel.get("com_const_rate") or 0, step=100)

        if st.button("Update Rates"):
            supabase.table("colonies").update({
                "res_land_rate": new_rl,
                "res_const_rate": new_rc,
                "com_land_rate": new_cl,
                "com_const_rate": new_cc,
            }).eq("colony_name", selected).execute()

            st.success("Rates updated successfully.")
            st.rerun()

    st.write("---")

    # ------------------------
    # DELETE COLONY
    # ------------------------
    st.write("### 🗑 Delete Colony")

    del_sel = st.selectbox("Select colony to delete", ["Select"] + colony_list)

    if st.button("Delete Colony"):
        if del_sel != "Select":
            supabase.table("colonies").delete().eq("colony_name", del_sel).execute()
            st.warning(f"{del_sel} deleted successfully!")
            st.rerun()

# -------------------------------------------------
# HISTORY TAB
# -------------------------------------------------

with tab_history:
    df = load_table("history")
    st.dataframe(df, use_container_width=True)

# -------------------------------------------------
# OTP TAB
# -------------------------------------------------

with tab_otps:
    df = load_table("otps")
    st.dataframe(df, use_container_width=True)

# -------------------------------------------------
# EVENTS TAB
# -------------------------------------------------

with tab_events:
    df = load_table("events")
    st.dataframe(df, use_container_width=True)
