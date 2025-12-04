import hashlib
from datetime import datetime

import pandas as pd
import streamlit as st

from database import get_connection, init_db

# -----------------------------------------
# BASIC CONFIG
# -----------------------------------------

st.set_page_config(
    page_title="Admin – Delhi Property Calculator",
    layout="wide",
)

st.markdown(
    """
    <style>
        .stApp {
            background: radial-gradient(circle at top, #182848, #03001e);
            color: #f5f7ff;
        }
        .admin-header {
            display:flex;
            align-items:center;
            gap:12px;
        }
        .admin-title {
            font-size:24px;
            font-weight:800;
            margin:0;
            color:#fdfcff;
        }
        .admin-sub {
            font-size:14px;
            margin:0;
            color:#c9d4ff;
        }
        .box {
            background: rgba(0, 0, 0, 0.45);
            padding: 18px 20px;
            border-radius: 12px;
            margin-bottom: 16px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------
# DB + HELPERS
# -----------------------------------------

init_db()
conn = get_connection()


def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def ensure_admin_session():
    if "admin_logged_in" not in st.session_state:
        st.session_state.admin_logged_in = False
    if "admin_email" not in st.session_state:
        st.session_state.admin_email = None


ensure_admin_session()

# -----------------------------------------
# ADMIN AUTH
# -----------------------------------------


def admin_login_ui():
    st.markdown(
        """
        <div class="admin-header">
            <div>
                <p class="admin-title">Admin Dashboard</p>
                <p class="admin-sub">Aggarwal Documents &amp; Legal Consultants</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("---")

    st.markdown('<div class="box">', unsafe_allow_html=True)
    st.subheader("🔐 Admin Login")

    admin_email_secret = st.secrets["admin"]["email"]
    admin_password_secret = st.secrets["admin"]["password"]

    email = st.text_input("Admin Email")
    password = st.text_input("Admin Password", type="password")

    if st.button("Login as Admin"):
        if email == admin_email_secret and password == admin_password_secret:
            st.session_state.admin_logged_in = True
            st.session_state.admin_email = email
            st.success("Admin login successful.")
            st.experimental_rerun()
        else:
            st.error("Invalid admin credentials.")

    st.markdown("</div>", unsafe_allow_html=True)


def require_admin():
    if not st.session_state.admin_logged_in:
        admin_login_ui()
        st.stop()


# -----------------------------------------
# ADMIN PAGES
# -----------------------------------------


def page_overview():
    st.markdown('<div class="box">', unsafe_allow_html=True)
    st.subheader("📊 Overview")

    c = conn.cursor()

    try:
        c.execute("SELECT COUNT(*) FROM users;")
        total_users = c.fetchone()[0]
    except Exception:
        total_users = "N/A"

    try:
        c.execute("SELECT COUNT(*) FROM history;")
        total_history = c.fetchone()[0]
    except Exception:
        total_history = "N/A"

    try:
        c.execute("SELECT COUNT(*) FROM colonies;")
        total_colonies = c.fetchone()[0]
    except Exception:
        total_colonies = "N/A"

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Users", total_users)
    with col2:
        st.metric("History Records", total_history)
    with col3:
        st.metric("Colonies", total_colonies)

    st.markdown("</div>", unsafe_allow_html=True)


def page_users():
    st.markdown('<div class="box">', unsafe_allow_html=True)
    st.subheader("👥 Manage Users")

    c = conn.cursor()
    try:
        df_users = pd.read_sql_query(
            "SELECT id, email, is_verified, created_at FROM users ORDER BY id DESC;",
            conn,
        )
        st.write("All registered users:")
        st.dataframe(df_users, use_container_width=True)
    except Exception as e:
        st.error("Error loading users table.")
        st.text(str(e))
        st.markdown("</div>", unsafe_allow_html=True)
        return

    st.write("---")
    col_create, col_reset, col_delete = st.columns(3)

    # ----- CREATE USER -----
    with col_create:
        st.markdown("#### ➕ Create User Manually")
        new_email = st.text_input("New User Email", key="admin_new_user_email")
        new_pw = st.text_input(
            "New User Password", type="password", key="admin_new_user_pw"
        )
        if st.button("Create User", key="btn_create_user"):
            if not new_email or not new_pw:
                st.error("Enter email and password.")
            else:
                try:
                    pw_hash = hash_password(new_pw)
                    c.execute(
                        """
                        INSERT INTO users (email, password_hash, is_verified, created_at)
                        VALUES (?, ?, ?, ?);
                        """,
                        (
                            new_email.lower(),
                            pw_hash,
                            1,
                            datetime.utcnow().isoformat(),
                        ),
                    )
                    conn.commit()
                    st.success(f"User '{new_email}' created.")
                    st.experimental_rerun()
                except Exception as e:
                    st.error("Error creating user.")
                    st.text(str(e))

    # ----- RESET PASSWORD -----
    with col_reset:
        st.markdown("#### 🔁 Reset User Password")
        reset_email = st.text_input(
            "User Email to Reset", key="admin_reset_email"
        )
        new_pw2 = st.text_input(
            "New Password", type="password", key="admin_reset_pw"
        )
        if st.button("Reset Password", key="btn_reset_pw"):
            if not reset_email or not new_pw2:
                st.error("Enter email and new password.")
            else:
                try:
                    pw_hash = hash_password(new_pw2)
                    c.execute(
                        "UPDATE users SET password_hash = ? WHERE email = ?;",
                        (pw_hash, reset_email.lower()),
                    )
                    conn.commit()
                    if c.rowcount == 0:
                        st.warning("No user found with that email.")
                    else:
                        st.success("Password updated.")
                except Exception as e:
                    st.error("Error updating password.")
                    st.text(str(e))

    # ----- DELETE USER -----
    with col_delete:
        st.markdown("#### 🗑️ Delete User")
        del_email = st.text_input(
            "User Email to Delete", key="admin_del_email"
        )
        if st.button("Delete User", key="btn_delete_user"):
            if not del_email:
                st.error("Enter email to delete.")
            else:
                try:
                    c.execute("DELETE FROM users WHERE email = ?;", (del_email.lower(),))
                    conn.commit()
                    if c.rowcount == 0:
                        st.warning("No user found with that email.")
                    else:
                        st.success("User deleted.")
                        st.experimental_rerun()
                except Exception as e:
                    st.error("Error deleting user.")
                    st.text(str(e))

    st.markdown("</div>", unsafe_allow_html=True)


def page_colonies():
    st.markdown('<div class="box">', unsafe_allow_html=True)
    st.subheader("🏙️ Manage Colonies")

    c = conn.cursor()
    try:
        df_cols = pd.read_sql_query(
            "SELECT id, colony_name, category FROM colonies ORDER BY colony_name;",
            conn,
        )
        st.write("Existing colonies:")
        st.dataframe(df_cols, use_container_width=True)
    except Exception as e:
        st.error("Error loading colonies.")
        st.text(str(e))
        st.markdown("</div>", unsafe_allow_html=True)
        return

    st.write("---")
    col_add, col_update, col_delete = st.columns(3)

    # ----- ADD COLONY -----
    with col_add:
        st.markdown("#### ➕ Add Colony")
        new_name = st.text_input("Colony Name", key="new_colony_name")
        new_cat = st.selectbox(
            "Category (A–H)",
            ["A", "B", "C", "D", "E", "F", "G", "H"],
            key="new_colony_cat",
        )
        if st.button("Add Colony", key="btn_add_colony"):
            if not new_name:
                st.error("Enter colony name.")
            else:
                try:
                    c.execute(
                        "INSERT INTO colonies (colony_name, category) VALUES (?, ?);",
                        (new_name.strip(), new_cat),
                    )
                    conn.commit()
                    st.success("Colony added.")
                    st.experimental_rerun()
                except Exception as e:
                    st.error("Error adding colony.")
                    st.text(str(e))

    # ----- UPDATE COLONY CATEGORY -----
    with col_update:
        st.markdown("#### ✏️ Update Category")
        upd_name = st.text_input(
            "Existing Colony Name", key="upd_colony_name"
        )
        upd_cat = st.selectbox(
            "New Category (A–H)",
            ["A", "B", "C", "D", "E", "F", "G", "H"],
            key="upd_colony_cat",
        )
        if st.button("Update Category", key="btn_upd_colony"):
            if not upd_name:
                st.error("Enter colony name.")
            else:
                try:
                    c.execute(
                        "UPDATE colonies SET category = ? WHERE colony_name = ?;",
                        (upd_cat, upd_name.strip()),
                    )
                    conn.commit()
                    if c.rowcount == 0:
                        st.warning("No colony found with that name.")
                    else:
                        st.success("Colony category updated.")
                        st.experimental_rerun()
                except Exception as e:
                    st.error("Error updating colony.")
                    st.text(str(e))

    # ----- DELETE COLONY -----
    with col_delete:
        st.markdown("#### 🗑️ Delete Colony")
        del_name = st.text_input(
            "Colony Name to Delete", key="del_colony_name"
        )
        if st.button("Delete Colony", key="btn_del_colony"):
            if not del_name:
                st.error("Enter colony name.")
            else:
                try:
                    c.execute(
                        "DELETE FROM colonies WHERE colony_name = ?;",
                        (del_name.strip(),),
                    )
                    conn.commit()
                    if c.rowcount == 0:
                        st.warning("No colony found with that name.")
                    else:
                        st.success("Colony deleted.")
                        st.experimental_rerun()
                except Exception as e:
                    st.error("Error deleting colony.")
                    st.text(str(e))

    st.markdown("</div>", unsafe_allow_html=True)


def page_history():
    st.markdown('<div class="box">', unsafe_allow_html=True)
    st.subheader("📚 Calculations History")

    c = conn.cursor()
    try:
        # Join with users to see email
        df_hist = pd.read_sql_query(
            """
            SELECT h.id,
                   h.created_at,
                   u.email AS user_email,
                   h.colony_name,
                   h.property_type,
                   h.category,
                   h.consideration,
                   h.stamp_duty,
                   h.e_fees,
                   h.tds,
                   h.total_govt_duty
            FROM history h
            LEFT JOIN users u ON h.user_id = u.id
            ORDER BY h.created_at DESC
            LIMIT 500;
            """,
            conn,
        )
        st.write("Last 500 history records:")
        st.dataframe(df_hist, use_container_width=True)
    except Exception as e:
        st.error("Error loading history table.")
        st.text(str(e))
        st.markdown("</div>", unsafe_allow_html=True)
        return

    st.write("---")
    st.markdown("#### 🗑️ Delete History Records")

    del_all = st.checkbox("Delete ALL history records (for all users)")
    del_user_email = st.text_input(
        "Or delete by user email (leave blank to skip)", key="hist_del_email"
    )

    if st.button("Delete Selected History", key="btn_del_hist"):
        try:
            if del_all:
                c.execute("DELETE FROM history;")
                conn.commit()
                st.success("All history records deleted.")
                st.experimental_rerun()
            elif del_user_email:
                c.execute(
                    """
                    DELETE FROM history
                    WHERE user_id IN (SELECT id FROM users WHERE email = ?);
                    """,
                    (del_user_email.lower(),),
                )
                conn.commit()
                st.success("History for that user deleted (if existed).")
                st.experimental_rerun()
            else:
                st.warning("Select 'Delete ALL' or enter a user email.")
        except Exception as e:
            st.error("Error deleting history.")
            st.text(str(e))

    st.markdown("</div>", unsafe_allow_html=True)


def page_otps():
    st.markdown('<div class="box">', unsafe_allow_html=True)
    st.subheader("📨 OTP Logs")

    try:
        df_otps = pd.read_sql_query(
            "SELECT * FROM otps ORDER BY created_at DESC LIMIT 200;", conn
        )
        st.write("Last 200 OTP records:")
        st.dataframe(df_otps, use_container_width=True)
    except Exception as e:
        st.warning(
            "Could not load OTP table. It may not exist or has a different structure."
        )
        st.text(str(e))

    st.markdown("</div>", unsafe_allow_html=True)


# -----------------------------------------
# MAIN ADMIN APP
# -----------------------------------------

require_admin()

header_col1, header_col2 = st.columns([3, 1])
with header_col1:
    st.markdown(
        """
        <div class="admin-header">
            <div>
                <p class="admin-title">Admin Dashboard</p>
                <p class="admin-sub">Logged in as: Admin</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with header_col2:
    if st.button("Logout", key="admin_logout"):
        st.session_state.admin_logged_in = False
        st.session_state.admin_email = None
        st.experimental_rerun()

st.write("---")

tab_overview, tab_users, tab_colonies, tab_history, tab_otps = st.tabs(
    ["📊 Overview", "👥 Users", "🏙️ Colonies", "📚 History", "📨 OTP Logs"]
)

with tab_overview:
    page_overview()

with tab_users:
    page_users()

with tab_colonies:
    page_colonies()

with tab_history:
    page_history()

with tab_otps:
    page_otps()
