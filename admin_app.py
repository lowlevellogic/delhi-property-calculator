# admin_app.py

import pandas as pd
import streamlit as st
from datetime import datetime, date
from supabase import create_client, Client

# -------------------------------------------------
# BASIC CONFIG & CONSTANTS
# -------------------------------------------------

st.set_page_config(
    page_title="Admin Dashboard – Delhi Property Calculator",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---- THEME / CSS (glass login + dark admin UI) ----
st.markdown(
    """
    <style>
        .stApp {
            background: radial-gradient(circle at top left, #1f2933 0, #020617 55%);
            color: #e5e7eb;
        }
        .main-title {
            font-size: 32px;
            font-weight: 900;
            color: #38bdf8;
            padding-bottom: 4px;
        }
        .sub-title {
            font-size: 15px;
            color: #9ca3af;
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
        .login-card {
            border-radius: 22px;
            padding: 30px 26px 26px 26px;
            background: linear-gradient(135deg,
                        rgba(15,23,42,0.92),
                        rgba(15,23,42,0.96));
            border: 1px solid rgba(56, 189, 248, 0.45);
            box-shadow: 0 18px 45px rgba(15,23,42,0.9);
        }
        .login-title {
            font-size: 22px;
            font-weight: 800;
            color: #f9fafb;
            margin-bottom: 2px;
        }
        .login-subtitle {
            font-size: 13px;
            color: #9ca3af;
            margin-bottom: 16px;
        }
        .login-badge {
            font-size: 11px;
            color: #38bdf8;
            text-transform: uppercase;
            letter-spacing: 0.12em;
        }
        .danger-text {
            color: #f97373;
            font-size: 13px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---- SUPABASE CLIENT ----

@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_supabase()

ADMIN_EMAIL = st.secrets["ADMIN_EMAIL"]
ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]

# ---- CATEGORY → RATE MAPS (same as main app) ----
CIRCLE_RATES_RES = {
    "A": 774000, "B": 245520, "C": 159840, "D": 127680,
    "E": 70080, "F": 56640, "G": 46200, "H": 23280,
}
CONSTRUCTION_RATES_RES = {
    "A": 21960, "B": 17400, "C": 13920, "D": 11160,
    "E": 9360, "F": 8220, "G": 6960, "H": 3480,
}
CIRCLE_RATES_COM = {k: v * 3 for k, v in CIRCLE_RATES_RES.items()}
CONSTRUCTION_RATES_COM = {
    "A": 25200, "B": 19920, "C": 15960, "D": 12840,
    "E": 10800, "F": 9480, "G": 8040, "H": 3960,
}

# -------------------------------------------------
# SESSION STATE
# -------------------------------------------------

if "admin_auth" not in st.session_state:
    st.session_state.admin_auth = False


# -------------------------------------------------
# HELPER – SUPABASE TABLE LOADER
# -------------------------------------------------

def load_table(name: str, select: str = "*") -> pd.DataFrame:
    """Load a table from Supabase into a DataFrame."""
    try:
        res = supabase.table(name).select(select).execute()
        rows = res.data or []
        return pd.DataFrame(rows)
    except Exception as e:
        st.error(f"Error loading table '{name}': {e}")
        return pd.DataFrame()


# -------------------------------------------------
# LOGIN PAGE (CENTERED GLASS CARD)
# -------------------------------------------------

def render_login_page():
    """Full-screen centered admin login."""
    st.markdown("<br><br>", unsafe_allow_html=True)
    col_left, col_center, col_right = st.columns([1, 1.1, 1])

    with col_center:
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

        email = st.text_input("Admin Email", key="admin_email_input")
        pw = st.text_input("Admin Password", type="password", key="admin_password_input")

        login_btn = st.button("Login as Admin", use_container_width=True)

        if login_btn:
            if email == ADMIN_EMAIL and pw == ADMIN_PASSWORD:
                st.session_state.admin_auth = True
                st.success("Login successful.")
                st.rerun()
            else:
                st.error("Invalid admin credentials.")

        st.markdown(
            "<p style='font-size:11px;color:#6b7280;margin-top:10px;'>"
            "Only trusted internal users should access this dashboard.</p>",
            unsafe_allow_html=True,
        )

        st.markdown("</div>", unsafe_allow_html=True)


# -------------------------------------------------
# IF NOT LOGGED IN → SHOW LOGIN + STOP
# -------------------------------------------------

if not st.session_state.admin_auth:
    # Empty sidebar for login page
    with st.sidebar:
        st.markdown("#### Admin Dashboard")
        st.caption("Login required to access data.")
    render_login_page()
    st.stop()


# -------------------------------------------------
# SIDEBAR WHEN LOGGED IN
# -------------------------------------------------

with st.sidebar:
    st.markdown("#### 🛡️ Admin")
    st.caption(f"Logged in as **{ADMIN_EMAIL}**")

    if st.button("Logout", use_container_width=True):
        st.session_state.admin_auth = False
        st.success("Logged out.")
        st.rerun()


# -------------------------------------------------
# HEADER
# -------------------------------------------------

st.markdown('<p class="main-title">🛡️ Admin Dashboard</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="sub-title">Internal dashboard for Delhi Property Price Calculator</p>',
    unsafe_allow_html=True,
)
st.write("---")


# -------------------------------------------------
# TABS
# -------------------------------------------------

tab_overview, tab_users, tab_colonies, tab_history, tab_otps, tab_events = st.tabs(
    ["📊 Overview", "👥 Users", "📌 Colonies", "📂 History", "🔑 OTP Logs", "📁 Events"]
)


# -------------------------------------------------
# OVERVIEW TAB
# -------------------------------------------------

with tab_overview:
    users_df = load_table("users", "id, email, created_at, last_login")
    history_df = load_table("history")
    events_df = load_table("events")
    otps_df = load_table("otps")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(
            f"""
            <div class="metric-box">
                <div class="big-number">{len(users_df)}</div>
                <div class="label">Total Users</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            f"""
            <div class="metric-box">
                <div class="big-number">{len(history_df)}</div>
                <div class="label">Saved Calculations</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            f"""
            <div class="metric-box">
                <div class="big-number">{len(otps_df)}</div>
                <div class="label">OTP Records</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col4:
        st.markdown(
            f"""
            <div class="metric-box">
                <div class="big-number">{len(events_df)}</div>
                <div class="label">Event Logs</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.write("### 👤 Latest Registered Users")

    if not users_df.empty:
        try:
            users_df["created_at"] = pd.to_datetime(
                users_df["created_at"], errors="coerce"
            )
            latest = users_df.sort_values("created_at", ascending=False).head(15)
        except Exception:
            latest = users_df.head(15)

        st.dataframe(latest, use_container_width=True)


# -------------------------------------------------
# USERS TAB – LIST + PER-USER HISTORY & DELETE
# -------------------------------------------------

with tab_users:
    st.subheader("👥 All Users")

    users = load_table("users")
    if users.empty:
        st.info("No users found.")
    else:
        search = st.text_input("Search user by email")
        df_show = users.copy()

        if search:
            df_show = df_show[df_show["email"].str.contains(search, case=False)]

        st.dataframe(df_show, use_container_width=True)

        # Per-user history + actions
        st.write("---")
        st.markdown("#### 🔍 User Details & History")

        email_options = ["(Select user)"] + sorted(df_show["email"].unique().tolist())
        selected_email = st.selectbox("Choose user", email_options)

        if selected_email != "(Select user)":
            user_row = users[users["email"] == selected_email].iloc[0]
            user_id = user_row["id"]

            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.metric("User Email", selected_email)
            with col_b:
                st.metric(
                    "Created At",
                    str(user_row.get("created_at", ""))[:19] if "created_at" in user_row else "-",
                )
            with col_c:
                st.metric(
                    "Last Login",
                    str(user_row.get("last_login", ""))[:19] if "last_login" in user_row else "-",
                )

            # Load this user's history
            user_hist = load_table("history")
            if not user_hist.empty and "user_id" in user_hist.columns:
                user_hist = user_hist[user_hist["user_id"] == user_id]
                if not user_hist.empty:
                    try:
                        user_hist["created_at"] = pd.to_datetime(
                            user_hist["created_at"], errors="coerce"
                        )
                        user_hist = user_hist.sort_values("created_at", ascending=False)
                    except Exception:
                        pass

                    st.markdown("##### 📂 This User's Calculation History")
                    st.dataframe(user_hist, use_container_width=True)
                else:
                    st.info("No history records for this user yet.")

            col_del1, col_del2 = st.columns(2)
            with col_del1:
                if st.button("🧹 Clear this user's history"):
                    try:
                        supabase.table("history").delete().eq("user_id", user_id).execute()
                        st.success("User history cleared.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error clearing history: {e}")

            with col_del2:
                if st.button("🗑️ Delete this user (and cascaded data)"):
                    try:
                        supabase.table("users").delete().eq("id", user_id).execute()
                        st.success("User deleted (history removed by cascade).")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error deleting user: {e}")


# -------------------------------------------------
# COLONIES TAB – LIST + SEARCH + DERIVED RATES
# -------------------------------------------------

with tab_colonies:
    st.subheader("📌 Colony List")

    colonies = load_table("colonies", "id, colony_name, category")
    if colonies.empty:
        st.info(
            "No colonies found yet. You can upload or insert from Supabase later; "
            "for now, the main app still works with CSV."
        )
    else:
        colonies["category"] = colonies["category"].astype(str).str.upper()

        # Add derived rates (not stored in DB – computed from category)
        def map_rate(cat, mapping):
            try:
                return mapping.get(cat, None)
            except Exception:
                return None

        colonies["res_land_rate"] = colonies["category"].apply(
            lambda c: map_rate(c, CIRCLE_RATES_RES)
        )
        colonies["res_const_rate"] = colonies["category"].apply(
            lambda c: map_rate(c, CONSTRUCTION_RATES_RES)
        )
        colonies["com_land_rate"] = colonies["category"].apply(
            lambda c: map_rate(c, CIRCLE_RATES_COM)
        )
        colonies["com_const_rate"] = colonies["category"].apply(
            lambda c: map_rate(c, CONSTRUCTION_RATES_COM)
        )

        search = st.text_input("Search colony")
        col_filter = st.multiselect(
            "Filter by category",
            options=sorted(colonies["category"].unique().tolist()),
            default=sorted(colonies["category"].unique().tolist()),
        )

        df_show = colonies.copy()
        if search:
            df_show = df_show[
                df_show["colony_name"].str.contains(search, case=False, na=False)
            ]
        if col_filter:
            df_show = df_show[df_show["category"].isin(col_filter)]

        st.dataframe(df_show, use_container_width=True)

        st.caption(
            "Rates shown here are derived from category using the same logic as the main app."
        )


# -------------------------------------------------
# HISTORY TAB – FILTERS + CLEAR ALL
# -------------------------------------------------

with tab_history:
    st.subheader("📂 Calculation History")

    hist_df = load_table("history")
    if hist_df.empty:
        st.info("No history records yet.")
    else:
        # Join with users to show email
        users = load_table("users", "id, email")
        id_to_email = dict(zip(users["id"], users["email"]))
        if "user_id" in hist_df.columns:
            hist_df["user_email"] = hist_df["user_id"].map(id_to_email)

        # Parse datetime
        if "created_at" in hist_df.columns:
            hist_df["created_at"] = pd.to_datetime(
                hist_df["created_at"], errors="coerce"
            )
        else:
            hist_df["created_at"] = pd.NaT

        # ---- FILTER BAR ----
        col_f1, col_f2, col_f3 = st.columns(3)

        with col_f1:
            email_opts = ["All"]
            if "user_email" in hist_df.columns:
                email_opts += sorted(
                    [e for e in hist_df["user_email"].dropna().unique().tolist()]
                )
            email_filter = st.selectbox("Filter by user", email_opts)

        with col_f2:
            if "property_type" in hist_df.columns:
                types = sorted(hist_df["property_type"].dropna().unique().tolist())
            else:
                types = []
            selected_types = st.multiselect(
                "Property type", options=types, default=types
            )

        with col_f3:
            valid_dates = hist_df["created_at"].dropna()
            if not valid_dates.empty:
                min_d = valid_dates.min().date()
                max_d = valid_dates.max().date()
            else:
                today = date.today()
                min_d = max_d = today

            date_range = st.date_input(
                "Date range",
                value=(min_d, max_d), key = "history_date_range"
            )

        # ---- APPLY FILTERS ----
        df_show = hist_df.copy()

        if email_filter != "All" and "user_email" in df_show.columns:
            df_show = df_show[df_show["user_email"] == email_filter]

        if selected_types and "property_type" in df_show.columns:
            df_show = df_show[df_show["property_type"].isin(selected_types)]

        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            start_d, end_d = date_range
            if "created_at" in df_show.columns:
                df_show = df_show[
                    (df_show["created_at"].dt.date >= start_d)
                    & (df_show["created_at"].dt.date <= end_d)
                ]

        # ---- SHOW TABLE ----
        try:
            df_show = df_show.sort_values("created_at", ascending=False)
        except Exception:
            pass

        st.dataframe(df_show, use_container_width=True)

        # ---- DANGER ZONE ----
        with st.expander("⚠️ Danger zone – clear ALL history"):
            st.markdown(
                "<span class='danger-text'>This will permanently remove all "
                "calculation history records.</span>",
                unsafe_allow_html=True,
            )
            if st.button("🧨 Delete ALL history records"):
                try:
                    supabase.table("history").delete().neq("id", 0).execute()
                    st.success("All history records deleted.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error deleting history: {e}")


# -------------------------------------------------
# OTP LOGS TAB
# -------------------------------------------------

with tab_otps:
    st.subheader("🔑 OTP Logs")
    df = load_table("otps")
    if df.empty:
        st.info("No OTP records yet.")
    else:
        try:
            if "created_at" in df.columns:
                df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
                df = df.sort_values("created_at", ascending=False)
        except Exception:
            pass

        st.dataframe(df, use_container_width=True)


# -------------------------------------------------
# EVENTS TAB – FILTERS + CLEAR ALL
# -------------------------------------------------

with tab_events:
    st.subheader("📁 Event Logs")
    df = load_table("events")
    if df.empty:
        st.info("No events recorded yet. (If this stays empty, ensure main app log_event() matches the events table schema.)")
    else:
        if "created_at" in df.columns:
            df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")

        # Map user_id → email if present
        users = load_table("users", "id, email")
        id_to_email = dict(zip(users["id"], users["email"]))
        if "user_id" in df.columns:
            df["user_email"] = df["user_id"].map(id_to_email)

        col_e1, col_e2, col_e3 = st.columns(3)

        with col_e1:
            types = sorted(df["event_type"].dropna().unique().tolist())
            selected_types = st.multiselect(
                "Event types", options=types, default=types
            )

        with col_e2:
            if "user_email" in df.columns:
                email_opts = ["All"] + sorted(
                    df["user_email"].dropna().unique().tolist()
                )
            else:
                email_opts = ["All"]
            email_filter = st.selectbox("User filter", email_opts)

        with col_e3:
            valid_dates = df["created_at"].dropna() if "created_at" in df.columns else []
            if not isinstance(valid_dates, list) and not valid_dates.empty:
                min_d = valid_dates.min().date()
                max_d = valid_dates.max().date()
            else:
                today = date.today()
                min_d = max_d = today
            date_range = st.date_input("Date range", value=(min_d, max_d), key = "events_date_range")

        df_show = df.copy()

        if selected_types:
            df_show = df_show[df_show["event_type"].isin(selected_types)]

        if email_filter != "All" and "user_email" in df_show.columns:
            df_show = df_show[df_show["user_email"] == email_filter]

        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            start_d, end_d = date_range
            if "created_at" in df_show.columns:
                df_show = df_show[
                    (df_show["created_at"].dt.date >= start_d)
                    & (df_show["created_at"].dt.date <= end_d)
                ]

        try:
            if "created_at" in df_show.columns:
                df_show = df_show.sort_values("created_at", ascending=False)
        except Exception:
            pass

        st.dataframe(df_show, use_container_width=True)

        with st.expander("⚠️ Danger zone – clear ALL events"):
            st.markdown(
                "<span class='danger-text'>This will remove every event log from the system.</span>",
                unsafe_allow_html=True,
            )
            if st.button("🧼 Delete ALL events"):
                try:
                    supabase.table("events").delete().neq("id", 0).execute()
                    st.success("All events deleted.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error deleting events: {e}")

