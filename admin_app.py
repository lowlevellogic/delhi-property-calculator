# admin_app.py – Admin Dashboard for Delhi Property Calculator
import pandas as pd
import streamlit as st
from datetime import datetime, date, timedelta
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

st.markdown(
    """ 
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
""",
    unsafe_allow_html=True,
)

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
# HELPERS
# -------------------------------------------------


def load_table(name: str, select: str = "*") -> pd.DataFrame:
    """Generic helper to load a table as DataFrame."""
    try:
        res = supabase.table(name).select(select).execute()
        return pd.DataFrame(res.data or [])
    except Exception as e:
        st.error(f"Error loading table {name}: {e}")
        return pd.DataFrame()


def parse_created_at(df: pd.DataFrame, col: str = "created_at") -> pd.DataFrame:
    """Ensure a datetime column & a date-only column exist for charts/filters."""
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")
        df["created_date"] = df[col].dt.date
    else:
        df["created_date"] = pd.NaT
    return df


# -------------------------------------------------
# LOGIN PAGE (PREMIUM)
# -------------------------------------------------


def render_login():
    st.markdown("<br><br><br>", unsafe_allow_html=True)

    with st.container():
        try:
            st.image("logo.jpg", width=130)
        except Exception:
            pass

        st.markdown('<div class="login-card">', unsafe_allow_html=True)

        st.markdown(
            """
            <div class="login-badge">Aggarwal Documents & Legal Consultants</div>
            <div class="login-title">Admin Control Panel</div>
            <div class="login-subtitle">
                Secure access to users, history, colony master & events.
            </div>
        """,
            unsafe_allow_html=True,
        )

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

st.markdown(
    "<h1 style='color:#38bdf8;'>🛡️ Admin Dashboard</h1>",
    unsafe_allow_html=True,
)
st.write("---")

# -------------------------------------------------
# TABS
# -------------------------------------------------

tab_overview, tab_users, tab_colonies, tab_history, tab_otps, tab_events = st.tabs(
    [
        "📊 Overview",
        "👥 Users",
        "📌 Colonies",
        "📂 History",
        "🔑 OTP Logs",
        "📁 Events",
    ]
)

# -------------------------------------------------
# OVERVIEW TAB
# -------------------------------------------------

with tab_overview:
    users_df = load_table("users")
    hist_df = load_table("history")
    otp_df = load_table("otps")
    ev_df = load_table("events")

    users_df = parse_created_at(users_df)
    ev_df = parse_created_at(ev_df)

    c1, c2, c3, c4 = st.columns(4)

    c1.markdown(
        f"<div class='metric-box'><div class='big-number'>{len(users_df)}</div><div class='label'>Users</div></div>",
        unsafe_allow_html=True,
    )
    c2.markdown(
        f"<div class='metric-box'><div class='big-number'>{len(hist_df)}</div><div class='label'>History Records</div></div>",
        unsafe_allow_html=True,
    )
    c3.markdown(
        f"<div class='metric-box'><div class='big-number'>{len(otp_df)}</div><div class='label'>OTP Logs</div></div>",
        unsafe_allow_html=True,
    )
    c4.markdown(
        f"<div class='metric-box'><div class='big-number'>{len(ev_df)}</div><div class='label'>Events</div></div>",
        unsafe_allow_html=True,
    )

    st.write("")

    # ---- Charts row: signups + traffic last 7 days ----
    col_a, col_b = st.columns(2)

    # Signups per day (last 7 days)
    with col_a:
        st.subheader("📈 Signups (last 7 days)")
        if not users_df.empty and "created_date" in users_df.columns:
            cutoff = date.today() - timedelta(days=6)
            u = users_df[users_df["created_date"] >= cutoff]
            if not u.empty:
                signup_counts = (
                    u.groupby("created_date")["id"].count().rename("signups")
                )
                signup_counts = signup_counts.reindex(
                    pd.date_range(cutoff, date.today()), fill_value=0
                )
                st.line_chart(signup_counts)
            else:
                st.info("No signups in the last 7 days.")
        else:
            st.info("No signup data available.")

    # Events per day (last 7 days)
    with col_b:
        st.subheader("📊 Traffic (events last 7 days)")
        if not ev_df.empty and "created_date" in ev_df.columns:
            cutoff = date.today() - timedelta(days=6)
            e = ev_df[ev_df["created_date"] >= cutoff]
            if not e.empty:
                ev_counts = (
                    e.groupby("created_date")["id"].count().rename("events")
                    if "id" in e.columns
                    else e.groupby("created_date")["event_type"]
                    .count()
                    .rename("events")
                )
                ev_counts = ev_counts.reindex(
                    pd.date_range(cutoff, date.today()), fill_value=0
                )
                st.area_chart(ev_counts)
            else:
                st.info("No events in the last 7 days.")
        else:
            st.info("No event data available.")

    st.write("---")
    st.write("### Latest Users")
    if not users_df.empty:
        st.dataframe(
            users_df.sort_values("created_at", ascending=False).head(10),
            use_container_width=True,
        )
    else:
        st.info("No users found.")

# -------------------------------------------------
# USERS TAB
# -------------------------------------------------

with tab_users:
    st.subheader("All Users")
    df = load_table("users")
    if df.empty:
        st.info("No users found.")
    else:
        search = st.text_input("Search by email")
        if search:
            df = df[df["email"].str.contains(search, case=False, na=False)]

        st.dataframe(df, use_container_width=True)

        st.write("---")
        st.subheader("User Details & History")

        user_list = ["Select user"] + sorted(df["email"].dropna().unique().tolist())
        selected_user = st.selectbox("Choose user", user_list)

        if selected_user != "Select user":
            user_row = df[df["email"] == selected_user].iloc[0]
            user_id = user_row["id"]

            st.metric("Email", selected_user)
            st.metric("Created", user_row.get("created_at", "-"))
            st.metric("Last Login", user_row.get("last_login", "-"))

            hist = load_table("history")
            hist = hist[hist["user_id"] == user_id]

            st.write("### User's Calculation History")
            if hist.empty:
                st.info("No history for this user.")
            else:
                st.dataframe(hist, use_container_width=True)

            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("Clear User History"):
                    supabase.table("history").delete().eq("user_id", user_id).execute()
                    st.success("History cleared")
                    st.rerun()

            with col_btn2:
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
        new_category = st.selectbox(
            "Category", list("ABCDEFGH"), key="new_colony_category"
        )

    if st.button("Add Colony"):
        if not new_colony:
            st.error("Enter colony name.")
        else:
            supabase.table("colonies").insert(
                {
                    "colony_name": new_colony,
                    "category": new_category,
                    "res_land_rate": None,
                    "res_const_rate": None,
                    "com_land_rate": None,
                    "com_const_rate": None,
                }
            ).execute()
            st.success("Colony added successfully.")
            st.rerun()

    st.write("---")

    # ------------------------
    # EDIT RATES
    # ------------------------
    st.write("### ✏ Update Colony Rates")

    colony_list = df["colony_name"].dropna().tolist()
    selected = st.selectbox("Select colony", ["Select colony"] + colony_list)

    if selected != "Select colony":
        sel = df[df["colony_name"] == selected].iloc[0]

        r1, r2 = st.columns(2)
        r3, r4 = st.columns(2)

        with r1:
            new_rl = st.number_input(
                "Residential Land Rate", value=sel.get("res_land_rate") or 0, step=100
            )
        with r2:
            new_rc = st.number_input(
                "Residential Construction Rate",
                value=sel.get("res_const_rate") or 0,
                step=100,
            )
        with r3:
            new_cl = st.number_input(
                "Commercial Land Rate", value=sel.get("com_land_rate") or 0, step=100
            )
        with r4:
            new_cc = st.number_input(
                "Commercial Construction Rate",
                value=sel.get("com_const_rate") or 0,
                step=100,
            )

        if st.button("Update Rates"):
            supabase.table("colonies").update(
                {
                    "res_land_rate": new_rl,
                    "res_const_rate": new_rc,
                    "com_land_rate": new_cl,
                    "com_const_rate": new_cc,
                }
            ).eq("colony_name", selected).execute()

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
    st.subheader("All History Records")
    df = load_table("history")
    if df.empty:
        st.info("No history records.")
    else:
        st.dataframe(df, use_container_width=True)

# -------------------------------------------------
# OTP TAB
# -------------------------------------------------

with tab_otps:
    st.subheader("OTP Logs")
    df = load_table("otps")
    if df.empty:
        st.info("No OTP logs.")
    else:
        st.dataframe(df, use_container_width=True)

# -------------------------------------------------
# EVENTS TAB – FILTERS + ANALYTICS
# -------------------------------------------------

with tab_events:
    st.subheader("Events (App Analytics)")

    df = load_table("events")
    if df.empty:
        st.info("No events logged yet.")
    else:
        df = parse_created_at(df)

        # ---- Filter row ----
        col_f1, col_f2, col_f3 = st.columns([1.3, 1, 1])

        with col_f1:
            min_date = df["created_date"].min() or date.today()
            max_date = df["created_date"].max() or date.today()
            date_range = st.date_input(
                "Date range",
                value=(min_date, max_date),
            )

        with col_f2:
            event_types = sorted(df["event_type"].dropna().unique().tolist())
            selected_types = st.multiselect(
                "Event types", options=event_types, default=event_types
            )

        with col_f3:
            email_search = st.text_input("Filter by email (contains)")

        # ---- Apply filters ----
        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_date, end_date = date_range
        else:
            start_date = df["created_date"].min()
            end_date = df["created_date"].max()

        mask = (df["created_date"] >= start_date) & (df["created_date"] <= end_date)

        if selected_types:
            mask &= df["event_type"].isin(selected_types)

        if email_search:
            mask &= df["email"].str.contains(email_search, case=False, na=False)

        df_filtered = df[mask].copy()

        st.write(
            f"Showing **{len(df_filtered)}** events "
            f"from **{start_date}** to **{end_date}**"
        )

        # ---- Small summary ----
        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            col_s1.metric("Unique visitors", df_filtered["email"].nunique())
        with col_s2:
            col_s2.metric(
                "Distinct event types", df_filtered["event_type"].nunique()
            )
        with col_s3:
            last_event_time = (
                df_filtered["created_at"].max() if "created_at" in df_filtered else "-"
            )
            col_s3.metric("Last event at", str(last_event_time))

        st.write("---")

        # ---- Event type distribution ----
        st.write("### Event Type Breakdown")
        type_counts = df_filtered["event_type"].value_counts().reset_index()
        type_counts.columns = ["event_type", "count"]
        st.bar_chart(type_counts.set_index("event_type"))

        st.write("### Raw Events")
        st.dataframe(df_filtered.sort_values("created_at", ascending=False), use_container_width=True)
