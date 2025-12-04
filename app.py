import math
import hashlib
from datetime import datetime
from urllib.parse import quote

import pandas as pd
import streamlit as st

from database import (
    get_connection,
    init_db,
    create_otp,
    verify_otp,
)
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
circlerates_com = {
    "A": 774000 * 3,
    "B": 245520 * 3,
    "C": 159840 * 3,
    "D": 127680 * 3,
    "E": 70080 * 3,
    "F": 56640 * 3,
    "G": 46200 * 3,
    "H": 23280 * 3,
}
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
        .admin-title {
            font-size: 24px;
            font-weight: 800;
            margin: 0;
            color: #fdfcff;
        }
        .admin-sub {
            font-size: 14px;
            margin: 0;
            color: #c9d4ff;
        }
        .box {
            background: rgba(0, 0, 0, 0.45);
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 20px;
        }
        .footer {
            text-align: center;
            margin-top: 30px;
            font-size: 13px;
            color: #d0e8ff;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------------------------------
# DB INIT & GLOBAL CONNECTION
# -------------------------------------------------

init_db()
conn = get_connection()

# -------------------------------------------------
# SHARED HELPERS
# -------------------------------------------------


def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def get_user_by_email(email: str):
    c = conn.cursor()
    c.execute(
        "SELECT id, email, password_hash, is_verified FROM users WHERE email = ?;",
        (email.lower(),),
    )
    return c.fetchone()


def create_user(email: str, password_hash: str):
    c = conn.cursor()
    c.execute(
        "INSERT INTO users (email, password_hash, is_verified, created_at) "
        "VALUES (?, ?, ?, ?);",
        (email.lower(), password_hash, 1, datetime.utcnow().isoformat()),
    )
    conn.commit()
    c.execute(
        "SELECT id, email, password_hash, is_verified FROM users WHERE email = ?;",
        (email.lower(),),
    )
    return c.fetchone()


def ensure_session_state():
    defaults = {
        "user_id": None,
        "user_email": None,
        "pending_signup_email": None,
        "otp_sent": False,
        "last_result": None,
        "last_result_tab": None,
        "admin_logged_in": False,
        "admin_email": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


ensure_session_state()

# -------------------------------------------------
# COLONIES FROM DB
# -------------------------------------------------


@st.cache_data
def load_colonies_from_db():
    df = pd.read_sql_query(
        "SELECT colony_name, category FROM colonies ORDER BY colony_name;",
        conn,
    )
    names = df["colony_name"].tolist()
    mapping = dict(zip(df["colony_name"], df["category"]))
    return names, mapping


COLONY_NAMES, COLONY_MAP = load_colonies_from_db()

# -------------------------------------------------
# CALC HELPERS
# -------------------------------------------------


def convert_sq_yards_to_sq_meters(sq_yards: float) -> float:
    return round(sq_yards * 0.8361, 2)


def age_multiplier(year: int) -> float:
    if year < 1960:
        return 0.5
    if 1960 <= year <= 1969:
        return 0.6
    if 1970 <= year <= 1979:
        return 0.7
    if 1980 <= year <= 1989:
        return 0.8
    if 1990 <= year <= 2000:
        return 0.9
    return 1.0


def get_stampduty_rate(owner: str, consideration: float) -> float:
    base = stampdutyrates.get(owner, 0)
    return base + 0.01 if consideration > 2_500_000 else base


def run_calculation(
    property_type: str,
    land_area_yards: float,
    category: str,
    owner: str,
    include_const: str,
    parking: str,
    total_storey: int,
    user_storey: int,
    constructed_area: float,
    year_built: int,
    custom_cons: float,
    colony_name: str | None = None,
):
    # Choose rate tables
    if property_type == "Residential":
        circlerates = circlerates_res
        construction_rates = construction_rates_res
    else:
        circlerates = circlerates_com
        construction_rates = construction_rates_com

    land_area_m = convert_sq_yards_to_sq_meters(land_area_yards)
    land_value_total = circlerates[category] * land_area_m
    storey_ratio = user_storey / total_storey
    land_value_user = land_value_total * storey_ratio

    construction_value = 0.0
    parking_cost = 0.0

    if include_const == "yes":
        constructed_area_m = convert_sq_yards_to_sq_meters(constructed_area)
        base_const = construction_rates[category] * constructed_area_m
        age_multi = age_multiplier(int(year_built))
        construction_value = base_const * age_multi * user_storey

        if parking == "yes":
            parking_cost = (
                land_area_m * construction_rates[category] * user_storey / total_storey
            )

    total_construction = construction_value + parking_cost
    auto_consideration = land_value_user + total_construction

    if custom_cons > 0:
        final_consideration = float(custom_cons)
        cons_source = "Custom consideration used"
    else:
        final_consideration = auto_consideration
        cons_source = "Auto consideration used (no custom value entered)"

    stamp_rate = get_stampduty_rate(owner, final_consideration)
    stamp_duty = final_consideration * stamp_rate

    if property_type == "Residential":
        mutation = 1136 if final_consideration > 5_000_000 else 1124
    else:
        mutation = 1124

    e_fees = final_consideration * 0.01 + mutation
    tds = final_consideration * 0.01 if final_consideration > 5_000_000 else 0.0
    total_payable = stamp_duty + e_fees + tds

    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "property_type": property_type,
        "colony_name": colony_name,
        "land_area_yards": land_area_yards,
        "land_area_m": land_area_m,
        "category": category,
        "owner": owner,
        "include_const": include_const,
        "parking": parking,
        "total_storey": total_storey,
        "user_storey": user_storey,
        "constructed_area": constructed_area,
        "year_built": year_built,
        "auto_consideration": auto_consideration,
        "custom_consideration": custom_cons,
        "final_consideration": final_consideration,
        "cons_source": cons_source,
        "stamp_rate": stamp_rate,
        "stamp_duty": stamp_duty,
        "mutation": mutation,
        "e_fees": e_fees,
        "tds": tds,
        "total_payable": total_payable,
        "land_value_user": land_value_user,
        "construction_value": construction_value,
        "parking_cost": parking_cost,
    }


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
) -> tuple[float, float]:
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
# HISTORY SAVE / SUMMARY BLOCK
# -------------------------------------------------


def save_history_to_db(res: dict):
    if st.session_state.user_id is None:
        st.error("Please login to save history.")
        return
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO history (
            user_id, created_at, colony_name,
            property_type, category,
            consideration, stamp_duty, e_fees, tds, total_govt_duty
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            st.session_state.user_id,
            res["timestamp"],
            res["colony_name"],
            res["property_type"],
            res["category"],
            res["final_consideration"],
            res["stamp_duty"],
            res["e_fees"],
            res["tds"],
            res["total_payable"],
        ),
    )
    conn.commit()
    st.success("Summary saved to History.")


def render_summary_block(res: dict, save_key: str):
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
    st.write(f"**Your Land Value:** ₹{math.ceil(res['land_value_user']):,}")
    st.write(f"**Construction Value:** ₹{math.ceil(res['construction_value']):,}")
    st.write(f"**Parking Cost:** ₹{math.ceil(res['parking_cost']):,}")
    st.write(
        f"**Auto Consideration (circle + construction):** "
        f"₹{math.ceil(res['auto_consideration']):,}"
    )

    if res["custom_consideration"] > 0:
        st.write(
            f"**Custom Consideration Entered:** "
            f"₹{math.ceil(res['custom_consideration']):,}"
        )

    st.write(
        f"**Final Consideration Used ({res['cons_source']}):** "
        f"₹{math.ceil(res['final_consideration']):,}"
    )

    st.write("---")
    st.write("### Govt. Duty Calculation")
    st.write(
        f"**Stamp Duty ({res['stamp_rate']*100:.3f}%):** "
        f"₹{math.ceil(res['stamp_duty']):,}"
    )
    st.write(f"**Mutation Fees:** ₹{math.ceil(res['mutation']):,}")
    st.write(f"**E-Fees (1% + mutation):** ₹{math.ceil(res['e_fees']):,}")
    st.write(f"**TDS:** ₹{math.ceil(res['tds']):,}")
    st.success(
        f"**Total Payable Govt. Duty: ₹{math.ceil(res['total_payable']):,}**"
    )

    if st.button("💾 Save This Summary to History", key=save_key):
        if st.session_state.user_id is None:
            st.error("Please login to save history.")
        else:
            save_history_to_db(res)

    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------------------------
# USER AUTH SIDEBAR
# -------------------------------------------------


def user_auth_sidebar():
    with st.sidebar:
        st.markdown("### 🔐 Account (User)")

        if st.session_state.user_id is None:
            tab_login, tab_signup = st.tabs(["Login", "Sign Up"])

            # ---------- LOGIN ----------
            with tab_login:
                email = st.text_input("Email", key="login_email")
                password = st.text_input(
                    "Password", type="password", key="login_pw"
                )
                if st.button("Login", key="login_btn"):
                    row = get_user_by_email(email)
                    if not row:
                        st.error("No account found with this email.")
                    else:
                        user_id, u_email, pw_hash, is_verified = row
                        if pw_hash != hash_password(password):
                            st.error("Incorrect password.")
                        elif not is_verified:
                            st.error("Account not verified. Please sign up again.")
                        else:
                            st.session_state.user_id = user_id
                            st.session_state.user_email = u_email
                            st.success(f"Logged in as {u_email}")

            # ---------- SIGNUP ----------
            with tab_signup:
                signup_email = st.text_input(
                    "Email for Signup", key="signup_email"
                )

                if st.button("Send OTP", key="send_otp_btn"):
                    if not signup_email:
                        st.error("Please enter an email.")
                    else:
                        existing = get_user_by_email(signup_email)
                        if existing:
                            st.error(
                                "This email is already registered. Please login."
                            )
                        else:
                            otp, err = send_otp_email(signup_email)
                            if err:
                                st.error(
                                    "Failed to send OTP. Check email settings."
                                )
                                st.text(str(err))
                            else:
                                create_otp(signup_email, otp)
                                st.session_state.pending_signup_email = signup_email
                                st.session_state.otp_sent = True
                                st.success("OTP sent to your email.")

                if st.session_state.otp_sent and st.session_state.pending_signup_email:
                    st.write(
                        f"OTP sent to: {st.session_state.pending_signup_email}"
                    )
                    otp_input = st.text_input("Enter OTP", key="otp_input")
                    new_password = st.text_input(
                        "Set Password", type="password", key="signup_pw"
                    )
                    if st.button(
                        "Verify OTP & Create Account", key="verify_otp_btn"
                    ):
                        if not otp_input or not new_password:
                            st.error("Please enter both OTP and password.")
                        else:
                            ok = verify_otp(
                                st.session_state.pending_signup_email, otp_input
                            )
                            if not ok:
                                st.error("Invalid or expired OTP.")
                            else:
                                pw_hash = hash_password(new_password)
                                user = create_user(
                                    st.session_state.pending_signup_email, pw_hash
                                )
                                st.session_state.user_id = user[0]
                                st.session_state.user_email = user[1]
                                st.session_state.otp_sent = False
                                st.session_state.pending_signup_email = None
                                st.success("Account created and logged in!")
        else:
            st.success(f"Logged in as: {st.session_state.user_email}")
            if st.button("Logout"):
                st.session_state.user_id = None
                st.session_state.user_email = None
                st.rerun()

# -------------------------------------------------
# USER APP UI
# -------------------------------------------------


def run_user_app():
    # HEADER
    header_col1, header_col2 = st.columns([1, 6])
    with header_col1:
        st.image("logo.jpg", width=70)
    with header_col2:
        st.markdown(
            """
            <div class="main-header">
                <div>
                    <p class="brand-title">Aggarwal Documents &amp; Legal Consultants</p>
                    <p class="brand-subtitle">Delhi Property Price Calculator</p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.write("---")

    # Sidebar user auth
    user_auth_sidebar()

    # MAIN TABS
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

    # ---------- HOME TAB ----------
    with tab_home:
        st.markdown(
            """
            <div class="box">
            <h3>Welcome to the Delhi Property Price Calculator</h3>
            <p>
            This tool helps you estimate Delhi property values and government
            duty amounts quickly.
            </p>
            <ul>
                <li>Use <b>Residential</b> / <b>Commercial</b> tabs for circle rate based calculations.</li>
                <li>Use <b>DDA/CGHS</b> tab for DDA &amp; CGHS flat calculations.</li>
                <li>Saving summaries &amp; history requires login, but calculators are free to use.</li>
            </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ---------- RESIDENTIAL TAB ----------
    with tab_res:
        st.markdown('<div class="box">', unsafe_allow_html=True)
        st.subheader("Residential Property Calculation")

        col1, col2 = st.columns(2)
        with col1:
            r_colony_choice = None
            if COLONY_NAMES:
                r_colony_choice = st.selectbox(
                    "Colony (type to search, optional)",
                    ["(Not using colony)"] + COLONY_NAMES,
                    key="r_colony",
                )
            r_land_area_yards = st.number_input(
                "Land Area (Sq. Yards)",
                value=50.0,
                min_value=1.0,
                step=1.0,
                key="r_land_area",
            )

            if r_colony_choice and r_colony_choice != "(Not using colony)":
                r_category = COLONY_MAP.get(r_colony_choice, "G")
                st.info(f"Detected Category: **{r_category}**")
            else:
                r_category = st.selectbox(
                    "Property Category (A–H)",
                    list(circlerates_res.keys()),
                    key="r_category",
                )

            r_total_storey = st.number_input(
                "Total Storeys",
                value=1,
                min_value=1,
                step=1,
                key="r_total_storey",
            )
            r_user_storey = st.number_input(
                "Storeys Buying",
                value=1,
                min_value=1,
                step=1,
                key="r_user_storey",
            )

        with col2:
            r_owner = st.selectbox(
                "Ownership Type", ["male", "female", "joint"], key="r_owner"
            )
            r_include_const = st.radio(
                "Includes Construction?", ["yes", "no"], key="r_include_const"
            )
            r_parking = st.radio("Parking Provided?", ["yes", "no"], key="r_parking")

        r_constructed_area = 0.0
        r_year_built = 2000
        if r_include_const == "yes":
            st.write("### 🧱 Construction Details")
            col3, col4 = st.columns(2)
            with col3:
                r_constructed_area = st.number_input(
                    "Constructed Area (Sq. Yards)",
                    value=50.0,
                    min_value=1.0,
                    step=1.0,
                    key="r_constructed_area",
                )
            with col4:
                r_year_built = st.number_input(
                    "Year of Construction",
                    value=2005,
                    min_value=1900,
                    max_value=2100,
                    step=1,
                    key="r_year_built",
                )

        st.write("### ✏️ Custom Consideration (Optional)")
        r_custom_cons = st.number_input(
            "Enter your own consideration (leave 0 for auto):",
            value=0,
            min_value=0,
            step=1000,
            key="r_custom_cons",
        )

        if st.button("Calculate Residential", key="calc_res"):
            res = run_calculation(
                "Residential",
                r_land_area_yards,
                r_category,
                r_owner,
                r_include_const,
                r_parking,
                r_total_storey,
                r_user_storey,
                r_constructed_area,
                r_year_built,
                r_custom_cons,
                colony_name=(
                    None
                    if not r_colony_choice
                    or r_colony_choice == "(Not using colony)"
                    else r_colony_choice
                ),
            )
            st.session_state.last_result = res
            st.session_state.last_result_tab = "Residential"
            st.success("Residential property calculation completed.")

        if (
            st.session_state.last_result
            and st.session_state.last_result_tab == "Residential"
        ):
            render_summary_block(st.session_state.last_result, save_key="save_res")

        st.markdown("</div>", unsafe_allow_html=True)

    # ---------- COMMERCIAL TAB ----------
    with tab_com:
        st.markdown('<div class="box">', unsafe_allow_html=True)
        st.subheader("Commercial Property Calculation")

        col1, col2 = st.columns(2)
        with col1:
            c_colony_choice = None
            if COLONY_NAMES:
                c_colony_choice = st.selectbox(
                    "Colony (type to search, optional)",
                    ["(Not using colony)"] + COLONY_NAMES,
                    key="c_colony",
                )
            c_land_area_yards = st.number_input(
                "Land Area (Sq. Yards)",
                value=50.0,
                min_value=1.0,
                step=1.0,
                key="c_land_area",
            )

            if c_colony_choice and c_colony_choice != "(Not using colony)":
                c_category = COLONY_MAP.get(c_colony_choice, "G")
                st.info(f"Detected Category: **{c_category}**")
            else:
                c_category = st.selectbox(
                    "Property Category (A–H)",
                    list(circlerates_com.keys()),
                    key="c_category",
                )

            c_total_storey = st.number_input(
                "Total Storeys",
                value=1,
                min_value=1,
                step=1,
                key="c_total_storey",
            )
            c_user_storey = st.number_input(
                "Storeys Buying",
                value=1,
                min_value=1,
                step=1,
                key="c_user_storey",
            )

        with col2:
            c_owner = st.selectbox(
                "Ownership Type", ["male", "female", "joint"], key="c_owner"
            )
            c_include_const = st.radio(
                "Includes Construction?", ["yes", "no"], key="c_include_const"
            )
            c_parking = st.radio("Parking Provided?", ["yes", "no"], key="c_parking")

        c_constructed_area = 0.0
        c_year_built = 2000
        if c_include_const == "yes":
            st.write("### 🧱 Construction Details")
            col3, col4 = st.columns(2)
            with col3:
                c_constructed_area = st.number_input(
                    "Constructed Area (Sq. Yards)",
                    value=50.0,
                    min_value=1.0,
                    step=1.0,
                    key="c_constructed_area",
                )
            with col4:
                c_year_built = st.number_input(
                    "Year of Construction",
                    value=2005,
                    min_value=1900,
                    max_value=2100,
                    step=1,
                    key="c_year_built",
                )

        st.write("### ✏️ Custom Consideration (Optional)")
        c_custom_cons = st.number_input(
            "Enter your own consideration (leave 0 for auto):",
            value=0,
            min_value=0,
            step=1000,
            key="c_custom_cons",
        )

        if st.button("Calculate Commercial", key="calc_com"):
            res = run_calculation(
                "Commercial",
                c_land_area_yards,
                c_category,
                c_owner,
                c_include_const,
                c_parking,
                c_total_storey,
                c_user_storey,
                c_constructed_area,
                c_year_built,
                c_custom_cons,
                colony_name=(
                    None
                    if not c_colony_choice
                    or c_colony_choice == "(Not using colony)"
                    else c_colony_choice
                ),
            )
            st.session_state.last_result = res
            st.session_state.last_result_tab = "Commercial"
            st.success("Commercial property calculation completed.")

        if (
            st.session_state.last_result
            and st.session_state.last_result_tab == "Commercial"
        ):
            render_summary_block(st.session_state.last_result, save_key="save_com")

        st.markdown("</div>", unsafe_allow_html=True)

    # ---------- DDA / CGHS TAB ----------
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
                "Also calculate on your own consideration value", value=False
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

    # ---------- HISTORY TAB ----------
    with tab_history:
        st.markdown('<div class="box">', unsafe_allow_html=True)
        st.subheader("Saved Summaries (History)")

        if st.session_state.user_id is None:
            st.error("Please login to view your history.")
        else:
            c = conn.cursor()
            c.execute(
                """
                SELECT created_at, colony_name, property_type, category,
                       consideration, stamp_duty, e_fees, tds, total_govt_duty
                FROM history
                WHERE user_id = ?
                ORDER BY created_at DESC;
                """,
                (st.session_state.user_id,),
            )
            rows = c.fetchall()
            if not rows:
                st.info("No saved entries yet.")
            else:
                df = pd.DataFrame(
                    rows,
                    columns=[
                        "Time",
                        "Colony",
                        "Type",
                        "Category",
                        "Consideration (₹)",
                        "Stamp Duty (₹)",
                        "E-Fees (₹)",
                        "TDS (₹)",
                        "Total Govt Duty (₹)",
                    ],
                )
                st.dataframe(df, use_container_width=True)

                if st.button("Clear My History"):
                    c.execute(
                        "DELETE FROM history WHERE user_id = ?;",
                        (st.session_state.user_id,),
                    )
                    conn.commit()
                    st.success("Your history has been cleared.")
                    st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    # ---------- ABOUT TAB ----------
    with tab_about:
        st.markdown('<div class="box">', unsafe_allow_html=True)
        st.subheader("About Aggarwal Documents & Legal Consultants")

        st.write(
            """
            This calculator helps estimate Delhi property values and government
            duties.

            **Aggarwal Documents & Legal Consultants**  
            - Property Documentation  
            - Sale Deeds & Agreements  
            - Registration & Legal Consultancy  
            """
        )

        st.write("---")
        st.write("### 🔗 Share this App")

        st.write("**App Link (copy & share):**")
        st.code(APP_URL, language="text")

        wa_text = (
            "Check this Delhi Property Price Calculator by Aggarwal Documents & Legal Consultants: "
        )
        encoded_message = quote(wa_text + APP_URL, safe="")
        wa_url = f"https://wa.me/?text={encoded_message}"

        st.write("Or share directly on WhatsApp:")
        st.markdown(
            f"""
            <a href="{wa_url}" target="_blank">
            <button style="padding:8px 16px; border-radius:8px; border:none;
                           background-color:#25D366; color:white; cursor:pointer;">
                🟢 Share on WhatsApp
            </button>
            </a>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("</div>", unsafe_allow_html=True)

    # FOOTER
    st.markdown(
        '<div class="footer">Created by <b>Rishav Singh</b> · Aggarwal Documents &amp; Legal Consultants</div>',
        unsafe_allow_html=True,
    )

# -------------------------------------------------
# ADMIN APP (INSIDE SAME FILE)
# -------------------------------------------------


def admin_login_ui():
    st.markdown(
        """
        <div class="main-header">
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
            st.rerun()
        else:
            st.error("Invalid admin credentials.")

    st.markdown("</div>", unsafe_allow_html=True)


def require_admin():
    if not st.session_state.admin_logged_in:
        admin_login_ui()
        st.stop()


def admin_page_overview():
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


def admin_page_users():
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

    # CREATE USER
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
                    st.rerun()
                except Exception as e:
                    st.error("Error creating user.")
                    st.text(str(e))

    # RESET PASSWORD
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

    # DELETE USER
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
                        st.rerun()
                except Exception as e:
                    st.error("Error deleting user.")
                    st.text(str(e))

    st.markdown("</div>", unsafe_allow_html=True)


def admin_page_colonies():
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

    # ADD COLONY
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
                    st.rerun()
                except Exception as e:
                    st.error("Error adding colony.")
                    st.text(str(e))

    # UPDATE COLONY
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
                        st.rerun()
                except Exception as e:
                    st.error("Error updating colony.")
                    st.text(str(e))

    # DELETE COLONY
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
                        st.rerun()
                except Exception as e:
                    st.error("Error deleting colony.")
                    st.text(str(e))

    st.markdown("</div>", unsafe_allow_html=True)


def admin_page_history():
    st.markdown('<div class="box">', unsafe_allow_html=True)
    st.subheader("📚 Calculations History")

    try:
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
        c = conn.cursor()
        try:
            if del_all:
                c.execute("DELETE FROM history;")
                conn.commit()
                st.success("All history records deleted.")
                st.rerun()
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
                st.rerun()
            else:
                st.warning("Select 'Delete ALL' or enter a user email.")
        except Exception as e:
            st.error("Error deleting history.")
            st.text(str(e))

    st.markdown("</div>", unsafe_allow_html=True)


def admin_page_otps():
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


def run_admin_app():
    require_admin()

    header_col1, header_col2 = st.columns([3, 1])
    with header_col1:
        st.markdown(
            """
            <div class="main-header">
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
            st.rerun()

    st.write("---")

    tab_overview, tab_users, tab_colonies, tab_history, tab_otps = st.tabs(
        ["📊 Overview", "👥 Users", "🏙️ Colonies", "📚 History", "📨 OTP Logs"]
    )

    with tab_overview:
        admin_page_overview()

    with tab_users:
        admin_page_users()

    with tab_colonies:
        admin_page_colonies()

    with tab_history:
        admin_page_history()

    with tab_otps:
        admin_page_otps()

# -------------------------------------------------
# MODE SWITCHER (SIDEBAR) – OPTION B
# -------------------------------------------------

with st.sidebar:
    mode = st.radio("App Mode", ["User Mode", "Admin Panel"], index=0)

# Run corresponding UI
if mode == "User Mode":
    run_user_app()
else:
    run_admin_app()
