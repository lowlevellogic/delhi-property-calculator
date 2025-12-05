import math
import hashlib
from datetime import datetime, timedelta
from urllib.parse import quote

import pandas as pd
import streamlit as st
from supabase import create_client, Client

from email_otp import send_otp_email

# -------------------------------------------------
# BASIC CONFIG
# -------------------------------------------------

APP_URL = "https://delhi-property-calculator-lkdbpzkcuch6l8cgpehdsi.streamlit.app"

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
            align-items: center;
            gap: 10px;
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
        }
        label { color: #ffffff !important; }
        .footer { text-align:center; margin-top:30px; color:#d0e8ff; }
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
        "pending_signup_email": None,
        "pending_otp_purpose": None,
        "otp_sent": False,
        "remember_me": False,
        "last_result": None,
        "last_result_tab": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


ensure_session_state()

# -------------------------------------------------
# EVENT TRACKER  (events table: email, event_type, details, created_at)
# -------------------------------------------------


def log_event(event_type: str, details: str = ""):
    try:
        supabase.table("events").insert(
            {
                "email": st.session_state.user_email or "guest",
                "event_type": event_type,
                "details": details,
                "created_at": datetime.utcnow().isoformat(),
            }
        ).execute()
    except Exception:
        # Avoid breaking the app on logging errors
        pass


log_event("visit", "User visited homepage")

# -------------------------------------------------
# DB HELPERS
# -------------------------------------------------


def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def get_user_by_email(email: str):
    resp = (
        supabase.table("users")
        .select("id, email, password_hash, is_verified")
        .eq("email", email.lower())
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


def create_user(email: str, password_hash: str):
    resp = (
        supabase.table("users")
        .insert(
            {
                "email": email.lower(),
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
        return st.error("Login required to save.")

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
    st.success("Saved to history.")

# -------------------------------------------------
# COLONIES CSV
# -------------------------------------------------


@st.cache_data
def load_colonies_from_csv():
    try:
        df = pd.read_csv("colonies.csv")
    except Exception:
        return [], {}

    df.columns = [c.strip().lower() for c in df.columns]
    df["colony_name"] = df["colony_name"].astype(str)
    df["category"] = df["category"].astype(str).str.upper()

    names = df["colony_name"].tolist()
    mapping = dict(zip(df["colony_name"], df["category"]))
    return names, mapping


COLONY_NAMES, COLONY_MAP = load_colonies_from_csv()

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


# ---------- DDA HELPERS ----------


def determine_area_category(plinth_area_sqm: float) -> str:
    if plinth_area_sqm <= 30:
        return "upto_30"
    elif plinth_area_sqm <= 50:
        return "30_50"
    elif plinth_area_sqm <= 100:
        return "50_100"
    else:
        return "above_100"


def dda_minimum_value(
    plinth_area_sqm: float,
    building_more_than_4_storeys: bool,
    usage: str,
):
    usage = usage.lower()
    if usage not in AREA_CATEGORY_RATES:
        raise ValueError("Usage must be 'residential' or 'commercial'.")

    if building_more_than_4_storeys:
        rate = UNIFORM_RATES_MORE_THAN_4[usage]
    else:
        category = determine_area_category(plinth_area_sqm)
        rate = AREA_CATEGORY_RATES[usage][category]

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
    st.write(f"**Land Value:** ₹{math.ceil(res['land_value_user']):,}")
    st.write(f"**Construction Value:** ₹{math.ceil(res['construction_value']):,}")
    st.write(f"**Parking Cost:** ₹{math.ceil(res['parking_cost']):,}")

    st.write("---")
    st.write(f"**Final Consideration:** ₹{math.ceil(res['final_consideration']):,}")
    st.write(f"**Stamp Duty:** ₹{math.ceil(res['stamp_duty']):,}")
    st.write(f"**Mutation Fees:** ₹{math.ceil(res['mutation']):,}")
    st.write(f"**E-Fees:** ₹{math.ceil(res['e_fees']):,}")
    st.write(f"**TDS:** ₹{math.ceil(res['tds']):,}")
    st.success(f"**Total Govt. Duty: ₹{math.ceil(res['total_payable']):,}**")

    if st.button("💾 Save This Summary", key=save_key):
        save_history_to_db(res)

    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------------------------
# AUTH SIDEBAR
# -------------------------------------------------


def auth_sidebar():
    with st.sidebar:
        st.markdown("### 🔐 Account")

        # ------- NOT LOGGED IN -------
        if st.session_state.user_id is None:
            tab_login, tab_signup, tab_reset = st.tabs(
                ["Login", "Sign Up", "Forgot Password"]
            )

            # LOGIN
            with tab_login:
                email = st.text_input("Email", key="login_email")
                password = st.text_input("Password", type="password", key="login_pw")
                remember = st.checkbox("Remember me", key="remember_me_check")

                if st.button("Login", key="login_btn"):
                    row = get_user_by_email(email)

                    if not row:
                        st.error("No account found.")
                    elif row["password_hash"] != hash_password(password):
                        st.error("Incorrect password.")
                    else:
                        # SAVE SESSION VALUES SAFELY
                        st.session_state["user_id"] = row["id"]
                        st.session_state["user_email"] = row["email"]
                        st.session_state["remember_me"] = remember

                        update_last_login(row["id"])
                        log_event("login", f"{row['email']} logged in")

                        st.success("Logged in!")
                        st.rerun()
            # SIGN UP
            with tab_signup:
                signup_email = st.text_input("Signup Email", key="signup_email")

                if st.button("Send OTP", key="send_signup_otp"):
                    if not signup_email:
                        st.error("Enter email.")
                    elif get_user_by_email(signup_email):
                        st.error("Email already registered.")
                    else:
                        otp, err = send_otp_email(signup_email)
                        if err:
                            st.error("OTP failed.")
                        else:
                            create_otp_record(signup_email, otp, "signup")
                            st.session_state.pending_signup_email = signup_email
                            st.session_state.pending_otp_purpose = "signup"
                            st.session_state.otp_sent = True
                            st.success("OTP sent.")

                if (
                    st.session_state.otp_sent
                    and st.session_state.pending_signup_email
                    and st.session_state.pending_otp_purpose == "signup"
                ):
                    otp_entry = st.text_input("Enter OTP", key="signup_otp")
                    pw_new = st.text_input(
                        "Set Password", type="password", key="signup_pw"
                    )

                    if st.button("Verify & Create Account", key="signup_verify_btn"):
                        if verify_otp_record(
                            st.session_state.pending_signup_email,
                            otp_entry,
                            "signup",
                        ):
                            pw_hash = hash_password(pw_new)
                            user = create_user(
                                st.session_state.pending_signup_email,
                                pw_hash,
                            )
                            st.session_state.user_id = user["id"]
                            st.session_state.user_email = user["email"]
                            log_event("signup", f"{user['email']} registered")
                            st.success("Account created!")
                            st.session_state.otp_sent = False
                            st.session_state.pending_signup_email = None
                            st.session_state.pending_otp_purpose = None
                        else:
                            st.error("Invalid OTP.")

            # FORGOT PW
            with tab_reset:
                reset_email = st.text_input(
                    "Registered Email", key="reset_email"
                )

                if st.button("Send Reset OTP", key="send_reset_otp_btn"):
                    if not reset_email:
                        st.error("Enter email.")
                    elif not get_user_by_email(reset_email):
                        st.error("Email not registered.")
                    else:
                        otp, err = send_otp_email(reset_email)
                        if err:
                            st.error("OTP failed.")
                        else:
                            create_otp_record(reset_email, otp, "reset")
                            st.session_state.pending_signup_email = reset_email
                            st.session_state.pending_otp_purpose = "reset"
                            st.session_state.otp_sent = True
                            st.success("Reset OTP sent.")

                if (
                    st.session_state.otp_sent
                    and st.session_state.pending_signup_email
                    and st.session_state.pending_otp_purpose == "reset"
                ):
                    otp2 = st.text_input("Enter OTP", key="reset_otp")
                    newpw = st.text_input(
                        "New Password", type="password", key="reset_new_pw"
                    )

                    if st.button("Reset Password", key="reset_pw_btn"):
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
                            log_event(
                                "password_reset",
                                st.session_state.pending_signup_email,
                            )
                            st.success("Password reset!")
                            st.session_state.otp_sent = False
                            st.session_state.pending_signup_email = None
                            st.session_state.pending_otp_purpose = None
                        else:
                            st.error("Invalid OTP.")

        # ------- LOGGED IN -------
        else:
            st.success(f"Logged in as {st.session_state.user_email}")

            if st.button("Logout", key="logout_btn"):
                log_event("logout", st.session_state.user_email)
                st.session_state.user_id = None
                st.session_state.user_email = None
                st.session_state.remember_me = False
                st.rerun()

# -------------------------------------------------
# HEADER
# -------------------------------------------------

col1, col2 = st.columns([1, 6])
with col1:
    st.image("logo.jpg", width=70)
with col2:
    st.markdown(
        """
        <div class="main-header">
            <p class="brand-title">Aggarwal Documents & Legal Consultants</p>
            <p class="brand-subtitle">Delhi Property Price Calculator</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.write("---")

# Sidebar auth
auth_sidebar()

# -------------------------------------------------
# MAIN TABS
# -------------------------------------------------

tab_home, tab_res, tab_com, tab_dda, tab_history, tab_about = st.tabs(
    [
        "🏠 Home",
        "📄 Residential",
        "🏬 Commercial",
        "🏢 DDA/CGHS Flats",
        "📚 History",
        "ℹ️ About",
    ]
)

# -------------------------------------------------
# HOME
# -------------------------------------------------

with tab_home:
    st.markdown(
        """
        <div class="box">
        <h3>Welcome to the Delhi Property Price Calculator</h3>
        <p>Use the tabs above to calculate Residential, Commercial and DDA/CGHS values.</p>
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
            st.info(f"Detected Category: {r_category}")
            log_event("colony_selected", r_colony)
        else:
            r_category = st.selectbox(
                "Manual Category", list(circlerates_res.keys()), key="r_manual_cat"
            )

        r_land = st.number_input(
            "Land Area (Sq. Yards)", value=50.0, key="r_land_area"
        )

        r_total = st.number_input(
            "Total Floors", min_value=1, value=1, key="r_total_floors"
        )
        r_buy = st.number_input(
            "Floors Buying", min_value=1, value=1, key="r_buy_floors"
        )

    with col2:
        r_owner = st.selectbox(
            "Owner Type", ["male", "female", "joint"], key="r_owner"
        )
        r_const = st.radio(
            "Includes Construction?", ["yes", "no"], key="r_const_radio"
        )
        r_parking = st.radio(
            "Parking?", ["yes", "no"], key="r_parking_radio"
        )

    r_area = 0.0
    r_year = 2000
    if r_const == "yes":
        col3, col4 = st.columns(2)
        with col3:
            r_area = st.number_input(
                "Construction Area (Sq. Yards)",
                value=50.0,
                key="r_const_area",
            )
        with col4:
            r_year = st.number_input(
                "Construction Year",
                value=2005,
                min_value=1900,
                max_value=2100,
                key="r_const_year",
            )

    r_custom = st.number_input(
        "Custom Consideration (₹)", value=0, key="r_custom_cons"
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
            st.info(f"Detected Category: {c_category}")
            log_event("colony_selected", c_colony)
        else:
            c_category = st.selectbox(
                "Manual Category",
                list(circlerates_com.keys()),
                key="c_manual_cat",
            )

        c_land = st.number_input(
            "Land Area (Sq. Yards)", value=50.0, key="c_land_area"
        )

        c_total = st.number_input(
            "Total Floors", min_value=1, value=1, key="c_total_floors"
        )
        c_buy = st.number_input(
            "Floors Buying", min_value=1, value=1, key="c_buy_floors"
        )

    with col2:
        c_owner = st.selectbox(
            "Owner Type", ["male", "female", "joint"], key="c_owner"
        )
        c_const = st.radio(
            "Includes Construction?", ["yes", "no"], key="c_const_radio"
        )
        c_parking = st.radio(
            "Parking?", ["yes", "no"], key="c_parking_radio"
        )

    c_area = 0.0
    c_year = 2000
    if c_const == "yes":
        col3, col4 = st.columns(2)
        with col3:
            c_area = st.number_input(
                "Construction Area (Sq. Yards)",
                value=50.0,
                key="c_const_area",
            )
        with col4:
            c_year = st.number_input(
                "Construction Year",
                value=2005,
                min_value=1900,
                max_value=2100,
                key="c_const_year",
            )

    c_custom = st.number_input(
        "Custom Consideration (₹)", value=0, key="c_custom_cons"
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
            key="dda_area_yards",
        )
        dda_usage_pretty = st.radio(
            "Usage Type",
            ["Residential", "Commercial"],
            horizontal=True,
            key="dda_usage",
        )
        dda_more_than_4 = st.radio(
            "Building has more than 4 storeys?",
            ["No", "Yes"],
            horizontal=True,
            key="dda_more_than_4",
        )
    with col2:
        dda_owner = st.selectbox(
            "Buyer Type (for Stamp Duty)",
            ["male", "female", "joint"],
            key="dda_owner",
        )
        dda_calc_custom = st.checkbox(
            "Also calculate on your own consideration value",
            value=False,
            key="dda_custom_checkbox",
        )
        dda_custom_cons = 0.0
        if dda_calc_custom:
            dda_custom_cons = st.number_input(
                "Enter your own consideration value (₹)",
                min_value=0.0,
                step=10000.0,
                key="dda_custom_cons",
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
        if usage_key == "residential":
            mutation_govt = 1136 if govt_value > 5_000_000 else 1124
        else:
            mutation_govt = 1124
        e_fees_govt = govt_value * 0.01 + mutation_govt
        tds_govt = govt_value * 0.01 if govt_value > 5_000_000 else 0.0
        total_govt = stamp_govt + e_fees_govt + tds_govt

        log_event("dda_calc", f"Usage={usage_key}, GovtValue={govt_value}")

        st.markdown('<div class="box">', unsafe_allow_html=True)
        st.write("## 🔹 Government (Circle) Value – DDA/CGHS")

        st.write(f"**Usage Type:** {dda_usage_pretty}")
        st.write(
            f"**Plinth Area:** {dda_area_yards:.2f} sq. yards "
            f"({plinth_area_sqm:.2f} sq. meters)"
        )
        st.write(f"**Rate Applied:** ₹{rate_per_sqm:,.2f} per sq. meter")
        if more_than_4_flag:
            st.write("**Storey Rule:** Uniform rate (more than 4 storeys)")
        else:
            st.write("**Storey Rule:** Up to 4 storeys (area category-based rate)")

        st.success(f"**Minimum Govt. Value (Built-up): ₹{govt_value:,.2f}**")

        st.write("---")
        st.write("### Govt. Duty on Govt. Value")
        st.write(f"**Stamp Duty Rate:** {duty_rate_govt*100:.2f}%")
        st.write(f"**Stamp Duty Amount:** ₹{math.ceil(stamp_govt):,}")
        st.write(f"**Mutation Fees:** ₹{mutation_govt:,}")
        st.write(f"**E-Fees (1% + mutation):** ₹{math.ceil(e_fees_govt):,}")
        if tds_govt > 0:
            st.write(f"**TDS (1% > ₹50L):** ₹{math.ceil(tds_govt):,}")
        else:
            st.write("**TDS (1% > ₹50L):** Not applicable")
        st.success(
            f"**Total Govt Liability on Govt Value: ₹{math.ceil(total_govt):,}**"
        )

        # Optional custom consideration
        if dda_calc_custom and dda_custom_cons > 0:
            st.write("---")
            st.write("### Govt. Duty on Your Custom Consideration")
            custom_cons = dda_custom_cons
            duty_rate_c = get_stampduty_rate(dda_owner, custom_cons)
            stamp_c = custom_cons * duty_rate_c
            if usage_key == "residential":
                mutation_c = 1136 if custom_cons > 5_000_000 else 1124
            else:
                mutation_c = 1124
            e_fees_c = custom_cons * 0.01 + mutation_c
            tds_c = custom_cons * 0.01 if custom_cons > 5_000_000 else 0.0
            total_c = stamp_c + e_fees_c + tds_c

            st.write(f"**Consideration Value:** ₹{custom_cons:,.2f}")
            st.write(f"**Stamp Duty Rate:** {duty_rate_c*100:.2f}%")
            st.write(f"**Stamp Duty Amount:** ₹{math.ceil(stamp_c):,}")
            st.write(f"**Mutation Fees:** ₹{mutation_c:,}")
            st.write(f"**E-Fees (1% + mutation):** ₹{math.ceil(e_fees_c):,}")
            if tds_c > 0:
                st.write(f"**TDS (1% > ₹50L):** ₹{math.ceil(tds_c):,}")
            else:
                st.write("**TDS (1% > ₹50L):** Not applicable")
            st.success(
                f"**Total Govt Liability on Custom Value: ₹{math.ceil(total_c):,}**"
            )

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------------------------
# HISTORY
# -------------------------------------------------

with tab_history:
    st.markdown('<div class="box">', unsafe_allow_html=True)
    st.subheader("Saved History")

    if st.session_state.user_id is None:
        st.error("Login required.")
    else:
        resp = (
            supabase.table("history")
            .select(
                "created_at, colony_name, property_type, category,"
                "consideration, stamp_duty, e_fees, tds, total_govt_duty"
            )
            .eq("user_id", st.session_state.user_id)
            .order("created_at", desc=True)
            .execute()
        )

        rows = resp.data or []
        if not rows:
            st.info("No history yet.")
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
    st.subheader("About Aggarwal Documents & Legal Consultants")
    st.write("Delhi Property Price Calculator – created by Rishav Singh.")

    st.write("---")
    st.write("**App Link:**")
    st.code(APP_URL)

    wa = quote(f"Use this Delhi Property Calculator:\n{APP_URL}")
    st.markdown(
        f'<a href="https://wa.me/?text={wa}"><button>Share on WhatsApp</button></a>',
        unsafe_allow_html=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------------------------
# FOOTER
# -------------------------------------------------

st.markdown(
    '<div class="footer">Created by <b>Rishav</b> · Aggarwal Documents & Legal Consultants</div>',
    unsafe_allow_html=True,
        )

