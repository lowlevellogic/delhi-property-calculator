# app.py – Delhi Property Price Calculator (with popup auth & usernames)
# FINAL VERSION – with Supabase-based colony master

import math
import hashlib
from datetime import datetime, timedelta, date
from urllib.parse import quote

import pandas as pd
import streamlit as st
from supabase import create_client, Client

from email_otp import send_otp_email

# -------------------------------------------------
# BASIC CONFIG
# -------------------------------------------------

APP_URL = "https://delhi-property-calculator-public.streamlit.app"

stampdutyrates = {"male": 0.06, "female": 0.04, "joint": 0.05}

# Residential circle & construction rates
circlerates_res = {
    "A": 774000,
    "B": 245520,
    "C": 159840,
    "D": 127680,
    "E": 70080,
    "F": 56640,
    "G": 46200,
    "H": 23280,
}
construction_rates_res = {
    "A": 21960,
    "B": 17400,
    "C": 13920,
    "D": 11160,
    "E": 9360,
    "F": 8220,
    "G": 6960,
    "H": 3480,
}

# Commercial circle & construction rates
circlerates_com = {k: v * 3 for k, v in circlerates_res.items()}
construction_rates_com = {
    "A": 25200,
    "B": 19920,
    "C": 15960,
    "D": 12840,
    "E": 10800,
    "F": 9480,
    "G": 8040,
    "H": 3960,
}

# DDA / CGHS built-up rates (per sq. mtr.)
AREA_CATEGORY_RATES = {
    "residential": {
        "upto_30": 50400,
        "30_50": 54480,
        "50_100": 66240,
        "above_100": 76200,
    },
    "commercial": {
        "upto_30": 57840,
        "30_50": 62520,
        "50_100": 75960,
        "above_100": 87360,
    },
}
UNIFORM_RATES_MORE_THAN_4 = {
    "residential": 87840,
    "commercial": 100800,
}

# -------------------------------------------------
# STREAMLIT PAGE CONFIG & THEME
# -------------------------------------------------

st.set_page_config(
    page_title="Delhi Property Price Calculator",
    layout="wide",
)

st.markdown(
    """
    <style>
        .stApp {
            background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
            color: #ffffff;
        }
        .main-header {
            display: flex;
            flex-direction: column;
            gap: 2px;
        }
        @media (min-width: 768px) {
            .main-header {
                flex-direction: row;
                align-items: baseline;
                gap: 10px;
            }
        }
        .brand-title {
            font-size: 22px;
            font-weight: 800;
            margin: 0;
            color: #edf9ff;
        }
        .brand-subtitle {
            font-size: 14px;
            margin: 0;
            color: #d4ecff;
        }
        .box {
            background: rgba(0,0,0,0.45);
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 20px;
            border: 1px solid rgba(255,255,255,0.08);
        }
        label { color: #ffffff !important; }
        .footer { text-align:center; margin-top:30px; color:#d0e8ff; }

        /* ---------- Auth popup ---------- */
        .auth-wrapper {
            display: flex;
            justify-content: center;
            margin-top: 30px;
            margin-bottom: 10px;
        }
        .auth-card {
            width: 100%;
            max-width: 480px;
            background: radial-gradient(circle at top, rgba(15,23,42,0.96), rgba(15,23,42,0.98));
            border-radius: 22px;
            padding: 22px 22px 18px 22px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.75);
            border: 1px solid rgba(148, 163, 184, 0.45);
        }
        .auth-heading {
            text-align: center;
            margin-bottom: 14px;
        }
        .auth-badge {
            font-size: 11px;
            color: #7dd3fc;
            text-transform: uppercase;
            letter-spacing: 0.16em;
        }
        .auth-title {
            font-size: 22px;
            font-weight: 800;
            color: #f9fafb;
            margin: 4px 0 2px 0;
        }
        .auth-subtitle {
            font-size: 13px;
            color: #9ca3af;
        }
        .auth-footer {
            font-size: 11px;
            color: #6b7280;
            margin-top: 10px;
            text-align: center;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------------------------------
# SUPABASE CLIENT
# -------------------------------------------------

@st.cache_resource
def get_supabase_client() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_supabase_client()

# -------------------------------------------------
# SESSION STATE
# -------------------------------------------------

def ensure_session_state():
    defaults = {
        "user_id": None,
        "user_email": None,
        "username": None,
        "pending_signup_email": None,
        "pending_otp_purpose": None,
        "otp_sent": False,
        "remember_me": False,
        "last_result": None,
        "last_result_tab": None,
        "show_auth_modal": True,
        "show_reset_form": False,
        "signup_username": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

ensure_session_state()

# -------------------------------------------------
# EVENT TRACKER
# -------------------------------------------------

def log_event(event_type: str, details: str = ""):
    """Insert analytics event into Supabase."""
    try:
        payload = {
            "email": st.session_state.user_email or "guest",
            "event_type": str(event_type or "unknown"),
            "details": str(details or ""),
            "created_at": datetime.utcnow().isoformat(),
        }
        supabase.table("events").insert(payload).execute()
    except Exception as e:
        print("EVENT LOG ERROR:", e)

# -------------------------------------------------
# DB HELPERS
# -------------------------------------------------

def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def get_user_by_email(email: str):
    resp = (
        supabase.table("users")
        .select("id, email, username, password_hash, is_verified")
        .eq("email", email.lower())
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None

def get_user_by_username(username: str):
    resp = (
        supabase.table("users")
        .select("id, email, username, password_hash, is_verified")
        .eq("username", username.lower())
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None

def get_user_by_email_or_username(identifier: str):
    ident = (identifier or "").strip().lower()
    if not ident:
        return None
    if "@" in ident:
        return get_user_by_email(ident)
    return get_user_by_username(ident)

def create_user(email: str, username: str, password_hash: str):
    resp = (
        supabase.table("users")
        .insert(
            {
                "email": email.lower(),
                "username": username.lower(),
                "password_hash": password_hash,
                "is_verified": True,
                "created_at": datetime.utcnow().isoformat(),
            }
        )
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None

def update_last_login(uid):
    try:
        supabase.table("users").update(
            {"last_login": datetime.utcnow().isoformat()}
        ).eq("id", uid).execute()
    except Exception:
        pass

def create_otp_record(email, otp, purpose="signup"):
    supabase.table("otps").insert(
        {
            "email": email.lower(),
            "otp_code": otp,
            "purpose": purpose,
            "used": False,
            "expires_at": (datetime.utcnow() + timedelta(minutes=10)).isoformat(),
        }
    ).execute()

def verify_otp_record(email, otp_code, purpose):
    now = datetime.utcnow().isoformat()
    resp = (
        supabase.table("otps")
        .select("id, used, expires_at")
        .eq("email", email.lower())
        .eq("otp_code", otp_code)
        .eq("purpose", purpose)
        .order("id", desc=True)
        .limit(1)
        .execute()
    )
    row = resp.data[0] if resp.data else None
    if not row:
        return False
    if row["used"] or row["expires_at"] < now:
        return False

    supabase.table("otps").update({"used": True}).eq("id", row["id"]).execute()
    return True

def save_history_to_db(res: dict):
    if st.session_state.user_id is None:
        return st.error("Please sign in to save this calculation to your history.")

    supabase.table("history").insert(
        {
            "user_id": st.session_state.user_id,
            "created_at": datetime.utcnow().isoformat(),
            "colony_name": res["colony_name"],
            "property_type": res["property_type"],
            "category": res["category"],
            "consideration": res["final_consideration"],
            "stamp_duty": res["stamp_duty"],
            "e_fees": res["e_fees"],
            "tds": res["tds"],
            "total_govt_duty": res["total_payable"],
        }
    ).execute()

    log_event("history_saved", f"{res['property_type']} - {res['colony_name']}")
    st.success("Saved to your account history.")

# -------------------------------------------------
# LOAD COLONIES FROM SUPABASE
# -------------------------------------------------

@st.cache_data
def load_colonies_from_db():
    try:
        res = supabase.table("colonies").select("*").order("colony_name").execute()
        data = res.data or []
        df = pd.DataFrame(data)
        if df.empty:
            return [], {}, df

        names = df["colony_name"].tolist()
        category_map = dict(zip(df["colony_name"], df["category"]))

        return names, category_map, df
    except Exception as e:
        st.error(f"Error loading colonies: {e}")
        return [], {}, pd.DataFrame()

COLONY_NAMES, COLONY_MAP, COLONY_FULL_DF = load_colonies_from_db()

# -------------------------------------------------
# CALC HELPERS
# -------------------------------------------------

def convert_sq_yards_to_sq_meters(y):
    return round(y * 0.8361, 2)

def age_multiplier(year):
    if year < 1960:
        return 0.5
    if year <= 1969:
        return 0.6
    if year <= 1979:
        return 0.7
    if year <= 1989:
        return 0.8
    if year <= 2000:
        return 0.9
    return 1.0

def get_stampduty_rate(owner, val):
    base = stampdutyrates.get(owner, 0)
    return base + 0.01 if val > 2_500_000 else base

def determine_area_category(plinth_area_sqm: float) -> str:
    if plinth_area_sqm <= 30:
        return "upto_30"
    elif plinth_area_sqm <= 50:
        return "30_50"
    elif plinth_area_sqm <= 100:
        return "50_100"
    return "above_100"

def dda_minimum_value(plinth_area_sqm, building_more_than_4_storeys, usage):
    usage = usage.lower()
    if usage not in AREA_CATEGORY_RATES:
        raise ValueError("Usage must be 'residential' or 'commercial'.")

    if building_more_than_4_storeys:
        rate = UNIFORM_RATES_MORE_THAN_4[usage]
    else:
        cat = determine_area_category(plinth_area_sqm)
        rate = AREA_CATEGORY_RATES[usage][cat]

    value = plinth_area_sqm * rate
    return rate, value

# -------------------------------------------------
# CALCULATION WRAPPER
# -------------------------------------------------

def run_calculation(**kwargs):
    log_event("calculation_run", f"{kwargs.get('property_type')} calculation started")
    return _calc(**kwargs)

def _calc(
    property_type,
    land_area_yards,
    category,
    owner,
    include_const,
    parking,
    total_storey,
    user_storey,
    constructed_area,
    year_built,
    custom_cons,
    colony_name=None,
):
    if property_type == "Residential":
        circle = circlerates_res
        con = construction_rates_res
    else:
        circle = circlerates_com
        con = construction_rates_com

    land_m = convert_sq_yards_to_sq_meters(land_area_yards)
    land_total = circle[category] * land_m
    land_user = land_total * (user_storey / total_storey)

    construction_value = 0.0
    parking_cost = 0.0

    if include_const == "yes":
        area_m = convert_sq_yards_to_sq_meters(constructed_area)
        base_const = con[category] * area_m
        construction_value = base_const * age_multiplier(year_built) * user_storey

        if parking == "yes":
            parking_cost = land_m * con[category] * user_storey / total_storey

    auto_cons = land_user + construction_value + parking_cost

    if custom_cons > 0:
        final = custom_cons
        source = "Custom consideration used"
    else:
        final = auto_cons
        source = "Auto consideration used"

    stamp_rate = get_stampduty_rate(owner, final)
    stamp = final * stamp_rate

    mutation = 1136 if (property_type == "Residential" and final > 5_000_000) else 1124
    e = final * 0.01 + mutation
    tds = final * 0.01 if final > 5_000_000 else 0
    total = stamp + e + tds

    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "property_type": property_type,
        "colony_name": colony_name,
        "land_area_yards": land_area_yards,
        "land_area_m": land_m,
        "category": category,
        "owner": owner,
        "include_const": include_const,
        "parking": parking,
        "total_storey": total_storey,
        "user_storey": user_storey,
        "constructed_area": constructed_area,
        "year_built": year_built,
        "auto_consideration": auto_cons,
        "custom_consideration": custom_cons,
        "final_consideration": final,
        "cons_source": source,
        "stamp_rate": stamp_rate,
        "stamp_duty": stamp,
        "mutation": mutation,
        "e_fees": e,
        "tds": tds,
        "total_payable": total,
        "land_value_user": land_user,
        "construction_value": construction_value,
        "parking_cost": parking_cost,
    }

# -------------------------------------------------
# SUMMARY BLOCK
# -------------------------------------------------

def render_summary_block(res, save_key):
    log_event("result_viewed", f"{res['property_type']} - {res['colony_name']}")
    st.markdown('<div class="box">', unsafe_allow_html=True)
    st.write("## 📊 Calculation Summary")

    if res["colony_name"]:
        st.write(f"**Colony:** {res['colony_name']}")

    st.write(f"**Property Type:** {res['property_type']}")
    st.write(f"**Category:** {res['category']}")
    st.write(
        f"**Land Area:** {res['land_area_yards']} sq. yards "
        f"({res['land_area_m']:.2f} sq. meters)"
    )
    st.write(f"**Land Value (Your Share):** ₹{math.ceil(res['land_value_user']):,}")
    st.write(f"**Construction Value:** ₹{math.ceil(res['construction_value']):,}")
    st.write(f"**Parking Cost:** ₹{math.ceil(res['parking_cost']):,}")

    st.write("---")
    st.write(f"**Final Consideration:** ₹{math.ceil(res['final_consideration']):,}")
    st.write(f"**Stamp Duty:** ₹{math.ceil(res['stamp_duty']):,}")
    st.write(f"**Mutation Fees:** ₹{math.ceil(res['mutation']):,}")
    st.write(f"**E-Fees:** ₹{math.ceil(res['e_fees']):,}")
    st.write(f"**TDS:** ₹{math.ceil(res['tds']):,}")
    st.success(f"**Total Govt. Duty: ₹{math.ceil(res['total_payable']):,}**")

    if st.button("💾 Save This Summary to My Account", key=save_key):
        save_history_to_db(res)

    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------------------------
# SIDEBAR STATUS
# -------------------------------------------------

def render_sidebar_status():
    with st.sidebar:
        st.markdown("### 👤 Account")

        if st.session_state.user_id is not None:
            display_name = st.session_state.username or st.session_state.user_email
            st.success(f"Signed in as **{display_name}**")
            if st.button("Logout", key="logout_btn_sidebar"):
                st.session_state.user_id = None
                st.session_state.user_email = None
                st.session_state.username = None
                st.session_state.show_auth_modal = True
                st.rerun()
        else:
            st.info("Using as guest.")
            if st.button("Login / Sign up", key="open_auth_from_sidebar"):
                st.session_state.show_auth_modal = True

# -------------------------------------------------
# AUTH POPUP
# -------------------------------------------------

def render_auth_modal():
    """Center popup for login / signup. Can be closed to continue as guest."""
    if not st.session_state.show_auth_modal:
        return
    if st.session_state.user_id is not None:
        return

    # Outer popup container
    st.markdown(
        '<div class="auth-wrapper"><div class="auth-card">',
        unsafe_allow_html=True,
    )

    # ---------- CENTERED LOGO ----------
    st.markdown(
        """
        <style>
        .center-logo-box {
            width: 100%;
            display: flex;
            justify-content: center;
            margin-bottom: 15px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="center-logo-box">', unsafe_allow_html=True)
    try:
        st.image("logo.jpg", width=120)
    except Exception:
        pass
    st.markdown("</div>", unsafe_allow_html=True)

    # ---------- Heading ----------
    st.markdown(
        """
        <div class="auth-heading">
            <div class="auth-badge">Rishav Singh • Aggarwal Documents & Legal Consultants</div>
            <div class="auth-title">Sign in to continue</div>
            <div class="auth-subtitle">
                Create a free account to save your calculations, or continue as a guest.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---------- Tabs ----------
    tab_login, tab_signup = st.tabs(["Login", "Sign Up"])

    # ---------- LOGIN ----------
    with tab_login:
        identifier = st.text_input(
            "Email or Username",
            key="login_identifier",
            placeholder="e.g. rishav@gmail.com or rishav123",
        )
        password = st.text_input(
            "Password",
            type="password",
            key="login_pw",
        )
        remember = st.checkbox(
            "Remember me on this device", key="remember_me_check"
        )

        if st.button("Forgot password?", key="forgot_pw_link"):
            st.session_state.show_reset_form = True

        if st.button("Login", key="login_btn", use_container_width=True):
            row = get_user_by_email_or_username(identifier)

            if not row:
                st.error("No account found with that email / username.")
            elif row["password_hash"] != hash_password(password):
                st.error("Incorrect password.")
            else:
                st.session_state.user_id = row["id"]
                st.session_state.user_email = row["email"]
                st.session_state.username = row.get("username")
                st.session_state.remember_me = remember
                st.session_state.show_auth_modal = False
                st.session_state.show_reset_form = False
                update_last_login(row["id"])
                st.success("Welcome back!")
                st.rerun()

        # Reset password flow…
        if st.session_state.show_reset_form:
            st.write("---")
            st.markdown("##### Reset your password")

            reset_identifier = st.text_input(
                "Registered Email or Username",
                key="reset_identifier",
            )

            if st.button("Send reset OTP", key="send_reset_otp_btn"):
                if not reset_identifier:
                    st.error("Enter email or username.")
                else:
                    email_to_use = None
                    if "@" in reset_identifier:
                        email_to_use = reset_identifier.lower()
                    else:
                        user = get_user_by_username(reset_identifier)
                        if user:
                            email_to_use = user["email"]

                    if email_to_use:
                        otp, err = send_otp_email(email_to_use)
                        if not err:
                            create_otp_record(email_to_use, otp, "reset")
                            st.session_state.pending_signup_email = email_to_use
                            st.session_state.pending_otp_purpose = "reset"
                            st.session_state.otp_sent = True
                            st.success("OTP sent to email.")

            if (
                st.session_state.otp_sent
                and st.session_state.pending_signup_email
                and st.session_state.pending_otp_purpose == "reset"
            ):
                otp2 = st.text_input("Enter reset OTP", key="reset_otp")
                newpw = st.text_input(
                    "New password", type="password", key="reset_new_pw"
                )

                if st.button("Confirm password reset", key="reset_pw_btn"):
                    if verify_otp_record(
                        st.session_state.pending_signup_email,
                        otp2,
                        "reset",
                    ):
                        supabase.table("users").update(
                            {"password_hash": hash_password(newpw)}
                        ).eq(
                            "email", st.session_state.pending_signup_email
                        ).execute()
                        st.success("Password updated. Login now.")
                        st.session_state.otp_sent = False
                        st.session_state.pending_signup_email = None
                        st.session_state.pending_otp_purpose = None
                        st.session_state.show_reset_form = False
                    else:
                        st.error("Invalid / expired OTP.")

    # ---------- SIGNUP ----------
    with tab_signup:
        signup_email = st.text_input(
            "Email address", key="signup_email"
        )
        signup_username = st.text_input(
            "Choose a username", key="signup_username_input"
        )

        if st.button("Send verification OTP", key="send_signup_otp_btn"):
            if not signup_email or not signup_username:
                st.error("Enter both email & username.")
            elif get_user_by_email(signup_email):
                st.error("Email already registered.")
            elif get_user_by_username(signup_username):
                st.error("Username already taken.")
            else:
                otp, err = send_otp_email(signup_email)
                if not err:
                    create_otp_record(signup_email, otp, "signup")
                    st.session_state.pending_signup_email = signup_email
                    st.session_state.pending_otp_purpose = "signup"
                    st.session_state.signup_username = signup_username
                    st.session_state.otp_sent = True
                    st.success("OTP sent. Verify to create account.")

        if (
            st.session_state.otp_sent
            and st.session_state.pending_signup_email
            and st.session_state.pending_otp_purpose == "signup"
        ):
            st.write("---")
            log_event("visit_home:, "User opened homepage")
            st.markdown("##### Verify OTP & create account")

            otp_entry = st.text_input("Enter OTP", key="signup_otp")
            final_username = st.text_input(
                "Confirm username",
                key="signup_username_confirm",
                value=st.session_state.signup_username,
            )
            pw_new = st.text_input(
                "Set password", type="password", key="signup_pw"
            )

            if st.button("Create my account", key="signup_verify_btn"):
                if verify_otp_record(
                    st.session_state.pending_signup_email,
                    otp_entry,
                    "signup",
                ):
                    pw_hash = hash_password(pw_new)
                    user = create_user(
                        st.session_state.pending_signup_email,
                        final_username,
                        pw_hash,
                    )
                    st.session_state.user_id = user["id"]
                    st.session_state.user_email = user["email"]
                    st.session_state.username = user["username"]
                    st.success("Account created!")
                    st.session_state.show_auth_modal = False
                    st.rerun()
                else:
                    st.error("Invalid / expired OTP.")

    # ---------- Guest button ----------
    st.write("")
    col_guest1, col_guest2 = st.columns([1, 1])
    with col_guest2:
        if st.button("Continue as guest", use_container_width=True):
            st.session_state.show_auth_modal = False

    st.markdown(
        "<div class='auth-footer'>Guest mode will not save history.</div>",
        unsafe_allow_html=True,
    )

    # Close wrapper
    st.markdown("</div></div>", unsafe_allow_html=True)

# -------------------------------------------------
# HEADER
# -------------------------------------------------

col1, col2, col3 = st.columns([1, 5, 2])
with col1:
    try:
        st.image("logo.jpg", width=70)
    except Exception:
        pass
with col2:
    st.markdown(
        """
        <div class="main-header">
            <p class="brand-title">Delhi Property Price Calculator</p>
            <p class="brand-subtitle">
                by Rishav Singh • Aggarwal Documents & Legal Consultants
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
with col3:
    if st.session_state.user_id is None:
        if st.button("🔐 Login / Sign up", key="open_auth_top"):
            st.session_state.show_auth_modal = True
    else:
        st.caption(
            f"Logged in as **{st.session_state.username or st.session_state.user_email}**"
        )

st.write("---")

render_sidebar_status()
render_auth_modal()

# -------------------------------------------------
# MAIN TABS
# -------------------------------------------------

tab_home, tab_res, tab_com, tab_dda, tab_history, tab_about = st.tabs(
    ["🏠 Home", "📄 Residential", "🏬 Commercial", "🏢 DDA/CGHS Flats", "📚 History", "ℹ️ About"]
)

# -------------------------------------------------
# HOME
# -------------------------------------------------

with tab_home:
    st.markdown(
        """
        <div class="box">
        <h3>Welcome to the Delhi Property Price Calculator</h3>
        <p>
        Quickly estimate government circle-rate value, stamp duty, mutation, e-fees and TDS
        for properties in Delhi.
        </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

# -------------------------------------------------
# RESIDENTIAL
# -------------------------------------------------

with tab_res:
    st.markdown('<div class="box">', unsafe_allow_html=True)
    st.subheader("Residential Property Calculation")

    col1, col2 = st.columns(2)
    with col1:
        r_colony = st.selectbox(
            "Colony (type to search)",
            ["(Not using colony)"] + COLONY_NAMES,
            key="r_colony",
        )

        if r_colony != "(Not using colony)":
            r_category = COLONY_MAP.get(r_colony, "G")
            st.info(f"Detected Category from master list: **{r_category}**")
        else:
            r_category = st.selectbox(
                "Manual Category", list(circlerates_res.keys()), key="r_manual_cat"
            )

        r_land = st.number_input("Land Area (Sq. Yards)", value=50.0, key="r_land_area")
        r_total = st.number_input(
            "Total Floors", min_value=1, value=1, key="r_total_floors"
        )
        r_buy = st.number_input(
            "Floors Purchased", min_value=1, value=1, key="r_buy_floors"
        )

    with col2:
        r_owner = st.selectbox(
            "Buyer Category", ["male", "female", "joint"], key="r_owner"
        )
        r_const = st.radio(
            "Includes Construction?", ["yes", "no"], key="r_const_radio"
        )
        r_parking = st.radio(
            "Parking Included?", ["yes", "no"], key="r_parking_radio"
        )

    r_area = 0.0
    r_year = 2000
    if r_const == "yes":
        col3, col4 = st.columns(2)
        with col3:
            r_area = st.number_input(
                "Construction Area (Sq. Yards)", value=50.0, key="r_const_area"
            )
        with col4:
            r_year = st.number_input(
                "Year of Construction",
                value=2005,
                min_value=1900,
                max_value=2100,
                key="r_const_year",
            )

    r_custom = st.number_input(
        "Custom Consideration (₹, optional)", value=0, key="r_custom_cons"
    )

    if st.button("Calculate Residential", key="calc_res_btn"):
        result = run_calculation(
            property_type="Residential",
            land_area_yards=r_land,
            category=r_category,
            owner=r_owner,
            include_const=r_const,
            parking=r_parking,
            total_storey=r_total,
            user_storey=r_buy,
            constructed_area=r_area,
            year_built=r_year,
            custom_cons=r_custom,
            colony_name=None if r_colony == "(Not using colony)" else r_colony,
        )
        st.session_state.last_result = result
        st.session_state.last_result_tab = "Residential"
        st.success("Residential calculation completed.")

    if (
        st.session_state.last_result is not None
        and st.session_state.last_result_tab == "Residential"
    ):
        render_summary_block(st.session_state.last_result, "save_res")

    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------------------------
# COMMERCIAL
# -------------------------------------------------

with tab_com:
    st.markdown('<div class="box">', unsafe_allow_html=True)
    st.subheader("Commercial Property Calculation")

    col1, col2 = st.columns(2)
    with col1:
        c_colony = st.selectbox(
            "Colony (type to search)",
            ["(Not using colony)"] + COLONY_NAMES,
            key="c_colony",
        )

        if c_colony != "(Not using colony)":
            c_category = COLONY_MAP.get(c_colony, "G")
            st.info(f"Detected Category from master list: **{c_category}**")
        else:
            c_category = st.selectbox(
                "Manual Category", list(circlerates_com.keys()), key="c_manual_cat"
            )

        c_land = st.number_input("Land Area (Sq. Yards)", value=50.0, key="c_land_area")
        c_total = st.number_input(
            "Total Floors", min_value=1, value=1, key="c_total_floors"
        )
        c_buy = st.number_input(
            "Floors Purchased", min_value=1, value=1, key="c_buy_floors"
        )

    with col2:
        c_owner = st.selectbox(
            "Buyer Category", ["male", "female", "joint"], key="c_owner"
        )
        c_const = st.radio(
            "Includes Construction?", ["yes", "no"], key="c_const_radio"
        )
        c_parking = st.radio(
            "Parking Included?", ["yes", "no"], key="c_parking_radio"
        )

    c_area = 0.0
    c_year = 2000
    if c_const == "yes":
        col3, col4 = st.columns(2)
        with col3:
            c_area = st.number_input(
                "Construction Area (Sq. Yards)", value=50.0, key="c_const_area"
            )
        with col4:
            c_year = st.number_input(
                "Year of Construction",
                value=2005,
                min_value=1900,
                max_value=2100,
                key="c_const_year",
            )

    c_custom = st.number_input(
        "Custom Consideration (₹, optional)", value=0, key="c_custom_cons"
    )

    if st.button("Calculate Commercial", key="calc_com_btn"):
        result = run_calculation(
            property_type="Commercial",
            land_area_yards=c_land,
            category=c_category,
            owner=c_owner,
            include_const=c_const,
            parking=c_parking,
            total_storey=c_total,
            user_storey=c_buy,
            constructed_area=c_area,
            year_built=c_year,
            custom_cons=c_custom,
            colony_name=None if c_colony == "(Not using colony)" else c_colony,
        )
        st.session_state.last_result = result
        st.session_state.last_result_tab = "Commercial"
        st.success("Commercial calculation completed.")

    if (
        st.session_state.last_result is not None
        and st.session_state.last_result_tab == "Commercial"
    ):
        render_summary_block(st.session_state.last_result, "save_com")

    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------------------------
# DDA / CGHS TAB
# -------------------------------------------------

with tab_dda:
    st.markdown('<div class="box">', unsafe_allow_html=True)
    st.subheader("DDA / CGHS Built-Up Flat Calculator")

    col1, col2 = st.columns(2)
    with col1:
        dda_area_yards = st.number_input(
            "Plinth Area (Sq. Yards)",
            min_value=1.0,
            value=50.0,
            step=1.0,
        )
        dda_usage_pretty = st.radio(
            "Usage Type", ["Residential", "Commercial"], horizontal=True
        )
        dda_more_than_4 = st.radio(
            "More than 4 floors?", ["No", "Yes"], horizontal=True
        )
    with col2:
        dda_owner = st.selectbox("Buyer Category", ["male", "female", "joint"])
        dda_calc_custom = st.checkbox("Calculate also on your consideration")
        dda_custom_cons = (
            st.number_input(
                "Custom Consideration (₹)", min_value=0.0, value=0.0
            )
            if dda_calc_custom
            else 0.0
        )

    if st.button("Calculate DDA / CGHS Value", key="dda_calc_btn"):
        usage_key = dda_usage_pretty.lower()
        more_than_4_flag = dda_more_than_4.lower() == "yes"

        plinth_area_sqm = convert_sq_yards_to_sq_meters(dda_area_yards)
        rate_per_sqm, govt_value = dda_minimum_value(
            plinth_area_sqm, more_than_4_flag, usage_key
        )

        duty_rate_govt = get_stampduty_rate(dda_owner, govt_value)
        stamp_govt = govt_value * duty_rate_govt
        mutation_govt = (
            1136 if (usage_key == "residential" and govt_value > 5_000_000) else 1124
        )
        e_fees_govt = govt_value * 0.01 + mutation_govt
        tds_govt = govt_value * 0.01 if govt_value > 5_000_000 else 0.0
        total_govt = stamp_govt + e_fees_govt + tds_govt

        log_event("dda_calc", f"Usage={usage_key}, GovtValue={govt_value}")

        st.markdown('<div class="box">', unsafe_allow_html=True)
        st.write("## 🔹 Government (Circle) Value – DDA/CGHS")
        st.write(f"Usage: **{dda_usage_pretty}**")
        st.write(
            f"Plinth Area: **{dda_area_yards} sq. yards ({plinth_area_sqm:.2f} sq. mtr)**"
        )
        st.write(f"Rate Applied: **₹{rate_per_sqm:,.2f}/sqm**")
        if more_than_4_flag:
            st.write("Storey Rule: **Uniform Rate (More than 4 floors)**")
        else:
            st.write("Storey Rule: **Up to 4 floors (Area Category Based)**")

        st.success(f"Minimum Govt Value: ₹{govt_value:,.2f}")

        st.write("---")
        st.write("### Govt. Duty on Govt. Value")
        st.write(f"Stamp Duty: ₹{math.ceil(stamp_govt):,}")
        st.write(f"Mutation Fees: ₹{mutation_govt:,}")
        st.write(f"E-Fees: ₹{math.ceil(e_fees_govt):,}")
        if tds_govt:
            st.write(f"TDS: ₹{math.ceil(tds_govt):,}")
        st.success(f"Total Govt Duty: ₹{math.ceil(total_govt):,}")

        if dda_calc_custom and dda_custom_cons > 0:
            st.write("---")
            st.write("### Govt Duty on Custom Value")
            custom_cons = dda_custom_cons

            duty_rate_c = get_stampduty_rate(dda_owner, custom_cons)
            stamp_c = custom_cons * duty_rate_c
            mutation_c = (
                1136 if (usage_key == "residential" and custom_cons > 5_000_000) else 1124
            )
            e_fees_c = custom_cons * 0.01 + mutation_c
            tds_c = custom_cons * 0.01 if custom_cons > 5_000_000 else 0.0
            total_c = stamp_c + e_fees_c + tds_c

            st.write(f"Consideration Value: ₹{custom_cons:,.2f}")
            st.write(f"Stamp: ₹{math.ceil(stamp_c):,}")
            st.write(f"Mutation: ₹{mutation_c:,}")
            st.write(f"E-Fees: ₹{math.ceil(e_fees_c):,}")
            st.success(f"Total Duty: ₹{math.ceil(total_c):,}")

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------------------------
# HISTORY
# -------------------------------------------------

with tab_history:
    st.markdown('<div class="box">', unsafe_allow_html=True)
    st.subheader("Saved History")

    if st.session_state.user_id is None:
        st.error("Please sign in.")
    else:
        resp = (
            supabase.table("history")
            .select(
                "created_at, colony_name, property_type, category, "
                "consideration, stamp_duty, e_fees, tds, total_govt_duty"
            )
            .eq("user_id", st.session_state.user_id)
            .order("created_at", desc=True)
            .execute()
        )

        rows = resp.data or []
        if not rows:
            st.info("No history saved.")
        else:
            df = pd.DataFrame(rows)
            df = df.rename(
                columns={
                    "created_at": "Time",
                    "colony_name": "Colony",
                    "property_type": "Type",
                    "category": "Category",
                    "consideration": "Consideration (₹)",
                    "stamp_duty": "Stamp Duty (₹)",
                    "e_fees": "E-Fees (₹)",
                    "tds": "TDS (₹)",
                    "total_govt_duty": "Total Govt Duty (₹)",
                }
            )
            st.dataframe(df, use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------------------------
# ABOUT
# -------------------------------------------------

with tab_about:
    st.markdown('<div class="box">', unsafe_allow_html=True)
    st.subheader("About this calculator")

    st.write(
        """
        This tool calculates:
        • Circle-rate values  
        • Construction value  
        • Stamp duty  
        • Mutation fees  
        • E-registration fees  
        • TDS  
        • DDA / CGHS built-up value  

        Designed by **Rishav Singh**  
        for **Aggarwal Documents & Legal Consultants**
    """
    )

    st.write("---")
    st.write("**Public app link:**")
    st.code(APP_URL)

    wa_text = (
        "Delhi Property Circle Rate & Govt Duty Calculator "
        "by Rishav Singh • Aggarwal Documents & Legal Consultants.%0A%0A"
        f"Use it here: {APP_URL}"
    )
    wa = quote(wa_text, safe=":/%")
    st.markdown(
        f'<a href="https://wa.me/?text={wa}"><button>📲 Share on WhatsApp</button></a>',
        unsafe_allow_html=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------------------------
# FOOTER
# -------------------------------------------------

st.markdown(
    '<div class="footer">© '
    f'{date.today().year} Rishav Singh · Aggarwal Documents & Legal Consultants</div>',
    unsafe_allow_html=True,
    )

