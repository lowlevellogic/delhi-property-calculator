# -------------------------------------------------
# app.py – Delhi Property Price Calculator
# FINAL CLEAN VERSION – PART 1/6
# -------------------------------------------------

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

# Residential Rates
circlerates_res = {
    "A": 774000, "B": 245520, "C": 159840, "D": 127680,
    "E": 70080, "F": 56640, "G": 46200, "H": 23280,
}
construction_rates_res = {
    "A": 21960, "B": 17400, "C": 13920, "D": 11160,
    "E": 9360, "F": 8220, "G": 6960, "H": 3480,
}

# Commercial Rates
circlerates_com = {k: v * 3 for k, v in circlerates_res.items()}
construction_rates_com = {
    "A": 25200, "B": 19920, "C": 15960, "D": 12840,
    "E": 10800, "F": 9480, "G": 8040, "H": 3960,
}

# DDA / CGHS Rates
AREA_CATEGORY_RATES = {
    "residential": {
        "upto_30": 50400, "30_50": 54480,
        "50_100": 66240, "above_100": 76200,
    },
    "commercial": {
        "upto_30": 57840, "30_50": 62520,
        "50_100": 75960, "above_100": 87360,
    },
}
UNIFORM_RATES_MORE_THAN_4 = {
    "residential": 87840,
    "commercial": 100800,
}

# -------------------------------------------------
# PAGE THEME & CSS
# -------------------------------------------------

st.set_page_config(page_title="Delhi Property Price Calculator", layout="wide")

st.markdown("""
<style>
.stApp { background: linear-gradient(135deg,#0f2027,#203a43,#2c5364); color:white; }
.box { background:rgba(0,0,0,0.45); padding:20px; border-radius:12px; margin-bottom:20px;
       border:1px solid rgba(255,255,255,0.12); }
.label, p, span { color:white !important; }

.auth-wrapper{ display:flex; justify-content:center; margin-top:20px; }
.auth-card{ width:100%; max-width:480px; background:rgba(10,17,28,0.9);
            padding:22px; border-radius:18px; border:1px solid rgba(255,255,255,0.15);
            box-shadow:0 18px 40px rgba(0,0,0,0.7); }
.center-logo-box{ display:flex; justify-content:center; margin-bottom:15px; }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------
# SUPABASE CLIENT
# -------------------------------------------------

@st.cache_resource
def get_supabase_client() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = get_supabase_client()

# -------------------------------------------------
# SESSION STATE
# -------------------------------------------------

def ensure_session_state():
    defaults = {
        "user_id": None, "user_email": None, "username": None,
        "pending_signup_email": None, "pending_otp_purpose": None,
        "otp_sent": False, "remember_me": False,
        "last_result": None, "last_result_tab": None,
        "show_auth_modal": True, "show_reset_form": False,
        "signup_username": "",
    }
    for k,v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

ensure_session_state()

# -------------------------------------------------
# EVENT LOGGER
# -------------------------------------------------

def log_event(event_type: str, details: str = ""):
    try:
        supabase.table("events").insert({
            "email": st.session_state.user_email or "guest",
            "event_type": event_type,
            "details": details,
            "created_at": datetime.utcnow().isoformat(),
        }).execute()
    except Exception as e:
        print("EVENT LOG ERROR:", e)

# -------------------------------------------------
# COLONY LOADER
# -------------------------------------------------

@st.cache_data
def load_colonies_from_db():
    try:
        res = supabase.table("colonies").select("*").order("colony_name").execute()
        df = pd.DataFrame(res.data or [])
        if df.empty:
            return [], {}, df
        return df["colony_name"].tolist(), dict(zip(df["colony_name"], df["category"])), df
    except:
        return [], {}, pd.DataFrame()

COLONY_NAMES, COLONY_MAP, COLONY_FULL_DF = load_colonies_from_db()

# -------------------------------------------------
# DB HELPERS
# -------------------------------------------------

def hash_password(pw: str):
    return hashlib.sha256(pw.encode()).hexdigest()

def get_user_by_email(email):
    r = supabase.table("users").select("*").eq("email", email.lower()).execute()
    return r.data[0] if r.data else None

def get_user_by_username(username):
    r = supabase.table("users").select("*").eq("username", username.lower()).execute()
    return r.data[0] if r.data else None

def get_user_by_email_or_username(identifier):
    identifier = identifier.strip().lower()
    if "@" in identifier:
        return get_user_by_email(identifier)
    return get_user_by_username(identifier)

def create_user(email, username, pw_hash):
    r = supabase.table("users").insert({
        "email": email.lower(),
        "username": username.lower(),
        "password_hash": pw_hash,
        "is_verified": True,
        "created_at": datetime.utcnow().isoformat(),
    }).execute()
    return r.data[0] if r.data else None

def update_last_login(uid):
    supabase.table("users").update({
        "last_login": datetime.utcnow().isoformat()
    }).eq("id", uid).execute()

def create_otp_record(email, otp, purpose):
    supabase.table("otps").insert({
        "email": email.lower(),
        "otp_code": otp,
        "purpose": purpose,
        "used": False,
        "expires_at": (datetime.utcnow() + timedelta(minutes=10)).isoformat(),
    }).execute()

def verify_otp_record(email, otp_code, purpose):
    now = datetime.utcnow().isoformat()
    r = supabase.table("otps").select("*") \
        .eq("email", email.lower()) \
        .eq("otp_code", otp_code) \
        .eq("purpose", purpose) \
        .order("id", desc=True).limit(1).execute()

    row = r.data[0] if r.data else None
    if not row or row["used"] or row["expires_at"] < now:
        return False

    supabase.table("otps").update({"used": True}).eq("id", row["id"]).execute()
    return True

def save_history_to_db(res):
    if not st.session_state.user_id:
        st.error("Please sign in first")
        return

    supabase.table("history").insert({
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
    }).execute()

    log_event("history_saved", f"{res['property_type']} - {res['colony_name']}")
    st.success("Saved to account.")

# -------------------------------------------------
# CALC HELPERS
# -------------------------------------------------

def convert_sq_yards_to_sq_meters(y):
    return round(y * 0.8361, 2)

def age_multiplier(year):
    if year < 1960: return 0.5
    if year <= 1969: return 0.6
    if year <= 1979: return 0.7
    if year <= 1989: return 0.8
    if year <= 2000: return 0.9
    return 1.0

def get_stampduty_rate(owner, val):
    base = stampdutyrates[owner]
    return base + 0.01 if val > 2_500_000 else base

def determine_area_category(area):
    if area <= 30: return "upto_30"
    if area <= 50: return "30_50"
    if area <= 100: return "50_100"
    return "above_100"

def dda_minimum_value(area_sqm, more_than_4, usage):
    if more_than_4:
        rate = UNIFORM_RATES_MORE_THAN_4[usage]
    else:
        cat = determine_area_category(area_sqm)
        rate = AREA_CATEGORY_RATES[usage][cat]
    return rate, rate * area_sqm

# -------------------------------------------------
# MAIN CALC
# -------------------------------------------------

def _calc(property_type, land_area_yards, category, owner,
          include_const, parking, total_storey, user_storey,
          constructed_area, year_built, custom_cons, colony_name=None):

    circle = circlerates_res if property_type=="Residential" else circlerates_com
    con = construction_rates_res if property_type=="Residential" else construction_rates_com

    land_m = convert_sq_yards_to_sq_meters(land_area_yards)
    land_user_value = circle[category] * land_m * (user_storey/total_storey)

    construction_value = 0
    parking_cost = 0

    if include_const == "yes":
        area_m = convert_sq_yards_to_sq_meters(constructed_area)
        construction_value = con[category] * area_m * age_multiplier(year_built)
        construction_value *= user_storey

        if parking == "yes":
            parking_cost = (con[category] * land_m * user_storey) / total_storey

    auto_cons = land_user_value + construction_value + parking_cost
    final = custom_cons if custom_cons > 0 else auto_cons

    stamp = final * get_stampduty_rate(owner, final)
    mutation = 1136 if (property_type=="Residential" and final>5_000_000) else 1124
    e_fees = final * 0.01 + mutation
    tds = final * 0.01 if final > 5_000_000 else 0
    total = stamp + e_fees + tds

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
        "stamp_duty": stamp,
        "mutation": mutation,
        "e_fees": e_fees,
        "tds": tds,
        "total_payable": total,
        "land_value_user": land_user_value,
        "construction_value": construction_value,
        "parking_cost": parking_cost,
    }

def run_calculation(**kw):
    log_event("calculation_run", kw.get("property_type"))
    return _calc(**kw)

# -------------------------------------------------
# SUMMARY BLOCK
# -------------------------------------------------

def render_summary_block(res, save_key):
    log_event("result_viewed", res["property_type"])

    st.markdown('<div class="box">', unsafe_allow_html=True)
    st.write("## 📊 Calculation Summary")

    for key,label in [
        ("colony_name", "Colony"),
        ("property_type", "Property Type"),
        ("category", "Category")
    ]:
        if res[key]:
            st.write(f"**{label}:** {res[key]}")

    st.write(f"**Land Area:** {res['land_area_yards']} sq yd ({res['land_area_m']:.2f} sq m)")
    st.write(f"**Land Value:** ₹{math.ceil(res['land_value_user']):,}")
    st.write(f"**Construction Value:** ₹{math.ceil(res['construction_value']):,}")
    st.write(f"**Parking Cost:** ₹{math.ceil(res['parking_cost']):,}")

    st.write("---")
    st.write(f"**Final Consideration:** ₹{math.ceil(res['final_consideration']):,}")
    st.write(f"**Stamp Duty:** ₹{math.ceil(res['stamp_duty']):,}")
    st.write(f"**Mutation Fees:** ₹{res['mutation']:,}")
    st.write(f"**E-Fees:** ₹{math.ceil(res['e_fees']):,}")
    st.write(f"TDS: ₹{math.ceil(res['tds']):,}")

    st.success(f"**Total Govt Duty: ₹{math.ceil(res['total_payable']):,}**")

    if st.button("💾 Save to My Account", key=save_key):
        save_history_to_db(res)

    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------------------------
# SIDEBAR LOGIN STATUS
# -------------------------------------------------

def render_sidebar_status():
    with st.sidebar:
        st.markdown("### 👤 Account")
        if st.session_state.user_id:
            st.success(f"Signed in as **{st.session_state.username}**")
            if st.button("Logout"):
                st.session_state.user_id = None
                st.session_state.user_email = None
                st.session_state.username = None
                st.session_state.show_auth_modal = True
                st.rerun()
        else:
            st.info("Browsing as guest.")
            if st.button("Login / Sign Up"):
                st.session_state.show_auth_modal = True

# -------------------------------------------------
# AUTH POPUP
# -------------------------------------------------

def render_auth_modal():
    if not st.session_state.show_auth_modal or st.session_state.user_id:
        return

    st.markdown('<div class="auth-wrapper"><div class="auth-card">', unsafe_allow_html=True)

    st.markdown('<div class="center-logo-box">', unsafe_allow_html=True)
    try: st.image("logo.jpg", width=100)
    except: pass
    st.markdown('</div>', unsafe_allow_html=True)

    tab_login, tab_signup = st.tabs(["Login", "Sign Up"])

    # ---------- LOGIN ----------
    with tab_login:
        email_or_user = st.text_input("Email or Username")
        pw = st.text_input("Password", type="password")

        if st.button("Login", use_container_width=True):
            user = get_user_by_email_or_username(email_or_user)
            if not user:
                st.error("Account not found.")
            elif user["password_hash"] != hash_password(pw):
                st.error("Wrong password.")
            else:
                st.session_state.user_id = user["id"]
                st.session_state.user_email = user["email"]
                st.session_state.username = user["username"]
                st.session_state.show_auth_modal = False
                update_last_login(user["id"])
                st.rerun()

        # Reset Password
        if st.button("Forgot password?"):
            st.session_state.show_reset_form = True

        if st.session_state.show_reset_form:
            st.write("### Reset Password")
            identifier = st.text_input("Registered Email or Username")

            if st.button("Send OTP"):
                user = get_user_by_email_or_username(identifier)
                if not user:
                    st.error("No such user")
                else:
                    otp, err = send_otp_email(user["email"])
                    if not err:
                        create_otp_record(user["email"], otp, "reset")
                        st.session_state.pending_signup_email = user["email"]
                        st.session_state.pending_otp_purpose = "reset"
                        st.session_state.otp_sent = True
                        st.success("OTP sent")

            if st.session_state.otp_sent and st.session_state.pending_otp_purpose=="reset":
                otp = st.text_input("Enter OTP")
                newpw = st.text_input("New Password", type="password")
                if st.button("Confirm Reset"):
                    if verify_otp_record(st.session_state.pending_signup_email, otp, "reset"):
                        supabase.table("users").update({
                            "password_hash": hash_password(newpw)
                        }).eq("email", st.session_state.pending_signup_email).execute()
                        st.success("Password updated")
                        st.session_state.otp_sent = False
                        st.session_state.show_reset_form = False
                    else:
                        st.error("Invalid OTP")

    # ---------- SIGNUP ----------
    with tab_signup:
        email = st.text_input("Email")
        username = st.text_input("Choose Username")
        if st.button("Send OTP"):
            if get_user_by_email(email):
                st.error("Email already registered")
            elif get_user_by_username(username):
                st.error("Username taken")
            else:
                otp, err = send_otp_email(email)
                if not err:
                    create_otp_record(email, otp, "signup")
                    st.session_state.pending_signup_email = email
                    st.session_state.pending_otp_purpose = "signup"
                    st.session_state.signup_username = username
                    st.session_state.otp_sent = True
                    st.success("OTP sent")

        if st.session_state.otp_sent and st.session_state.pending_otp_purpose=="signup":
            otp = st.text_input("Enter OTP")
            pw = st.text_input("Set Password", type="password")
            if st.button("Create Account"):
                if verify_otp_record(st.session_state.pending_signup_email, otp, "signup"):
                    user = create_user(
                        st.session_state.pending_signup_email,
                        st.session_state.signup_username,
                        hash_password(pw),
                    )
                    st.session_state.user_id = user["id"]
                    st.session_state.user_email = user["email"]
                    st.session_state.username = user["username"]
                    st.session_state.show_auth_modal=False
                    st.rerun()
                else:
                    st.error("Invalid OTP")

    # ---------- Guest ----------
    if st.button("Continue as Guest", use_container_width=True):
        st.session_state.show_auth_modal = False

    st.markdown("</div></div>", unsafe_allow_html=True)

# -------------------------------------------------
# HEADER
# -------------------------------------------------

col1,col2,col3 = st.columns([1,5,2])
with col1:
    try: st.image("logo.jpg", width=70)
    except: pass
with col2:
    st.markdown("""
    <div class='main-header'>
      <p class='brand-title'>Delhi Property Price Calculator</p>
      <p class='brand-subtitle'>by Rishav Singh – Aggarwal Documents & Legal Consultants</p>
    </div>
    """, unsafe_allow_html=True)
with col3:
    if not st.session_state.user_id:
        if st.button("🔐 Login / Sign Up"): st.session_state.show_auth_modal=True
    else:
        st.caption(f"Logged in as **{st.session_state.username}**")

st.write("---")

render_sidebar_status()
render_auth_modal()

# -------------------------------------------------
# MAIN TABS
# -------------------------------------------------

tab_home, tab_res, tab_com, tab_dda, tab_history, tab_about = st.tabs([
    "🏠 Home", "📄 Residential", "🏬 Commercial", "🏢 DDA/CGHS Flats",
    "📚 History", "ℹ️ About"
])

# -------------------------------------------------
# HOME
# -------------------------------------------------

with tab_home:
    st.markdown("""
    <div class='box'>
      <h3>Welcome to the Delhi Property Price Calculator</h3>
      <p>Calculate circle rates, stamp duty, mutation, TDS and more.</p>
    </div>""", unsafe_allow_html=True)

# -------------------------------------------------
# RESIDENTIAL
# -------------------------------------------------

with tab_res:
    st.markdown("<div class='box'>", unsafe_allow_html=True)
    st.subheader("Residential Property Calculation")

    col1,col2 = st.columns(2)

    with col1:
        colony = st.selectbox("Colony", ["(Not using colony)"] + COLONY_NAMES)
        if colony!="(Not using colony)":
            category = COLONY_MAP[colony]
            st.info(f"Category auto-detected: **{category}**")
        else:
            category = st.selectbox("Manual Category", list(circlerates_res.keys()))

        land = st.number_input("Land Area (sq yd)", 1.0, value=50.0)
        total = st.number_input("Total Floors",1,value=1)
        buy = st.number_input("Floors Purchased",1,value=1)

    with col2:
        owner = st.selectbox("Buyer Category",["male","female","joint"])
        include = st.radio("Includes Construction?",["yes","no"])
        parking = st.radio("Parking Included?",["yes","no"])

    area=0; year=2000
    if include=="yes":
        col3,col4 = st.columns(2)
        with col3:
            area = st.number_input("Construction Area (sq yd)",1.0,value=50.0)
        with col4:
            year = st.number_input("Year of Construction",1900,2100,2005)

    custom = st.number_input("Custom Consideration (₹)",0,value=0)

    if st.button("Calculate Residential"):
        res = run_calculation(
            property_type="Residential",
            land_area_yards=land, category=category, owner=owner,
            include_const=include, parking=parking,
            total_storey=total, user_storey=buy,
            constructed_area=area, year_built=year,
            custom_cons=custom,
            colony_name=None if colony=="(Not using colony)" else colony,
        )
        st.session_state.last_result=res
        st.session_state.last_result_tab="res"

    if st.session_state.last_result_tab=="res":
        render_summary_block(st.session_state.last_result,"save_res")

    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------------------------
# COMMERCIAL
# -------------------------------------------------

with tab_com:
    st.markdown("<div class='box'>", unsafe_allow_html=True)
    st.subheader("Commercial Property Calculation")

    col1,col2 = st.columns(2)
    with col1:
        colony = st.selectbox("Colony", ["(Not using colony)"] + COLONY_NAMES, key="c_colony")
        if colony!="(Not using colony)":
            category = COLONY_MAP[colony]
            st.info(f"Category auto: **{category}**")
        else:
            category = st.selectbox("Manual Category", list(circlerates_com.keys()))
        land = st.number_input("Land Area (sq yd)",1.0, value=50.0)
        total = st.number_input("Total Floors",1,value=1)
        buy = st.number_input("Floors Purchased",1,value=1)

    with col2:
        owner = st.selectbox("Buyer Category",["male","female","joint"], key="c_owner")
        include = st.radio("Includes Construction?",["yes","no"], key="c_inc")
        parking = st.radio("Parking Included?",["yes","no"], key="c_parking")

    area=0; year=2000
    if include=="yes":
        col3,col4 = st.columns(2)
        with col3:
            area = st.number_input("Construction Area (sq yd)",1.0,value=50.0, key="c_area")
        with col4:
            year = st.number_input("Year of Construction",1900,2100,2005, key="c_year")

    custom = st.number_input("Custom Consideration ₹",0,value=0, key="c_custom")

    if st.button("Calculate Commercial"):
        res = run_calculation(
            property_type="Commercial",
            land_area_yards=land, category=category, owner=owner,
            include_const=include, parking=parking,
            total_storey=total, user_storey=buy,
            constructed_area=area, year_built=year,
            custom_cons=custom,
            colony_name=None if colony=="(Not using colony)" else colony,
        )
        st.session_state.last_result=res
        st.session_state.last_result_tab="com"

    if st.session_state.last_result_tab=="com":
        render_summary_block(st.session_state.last_result,"save_com")

    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------------------------
# DDA/CGHS
# -------------------------------------------------

with tab_dda:
    st.markdown("<div class='box'>", unsafe_allow_html=True)
    st.subheader("DDA / CGHS Built-Up Flat Calculator")

    col1,col2 = st.columns(2)
    with col1:
        plinth = st.number_input("Plinth Area (sq yd)",1.0,value=50.0)
        usage_pretty = st.radio("Usage",["Residential","Commercial"])
        more_than_4 = st.radio("More than 4 floors?",["No","Yes"])
    with col2:
        owner = st.selectbox("Buyer Category",["male","female","joint"])
        custom_flag = st.checkbox("Calculate also on custom consideration")
        custom_value = st.number_input("Custom Consideration ₹",0.0,value=0.0) if custom_flag else 0

    if st.button("Calculate DDA"):
        usage = usage_pretty.lower()
        more_flag = (more_than_4=="Yes")

        sqm = convert_sq_yards_to_sq_meters(plinth)
        rate, govt_value = dda_minimum_value(sqm, more_flag, usage)

        stamp = govt_value * get_stampduty_rate(owner, govt_value)
        mutation = 1136 if (usage=="residential" and govt_value>5_000_000) else 1124
        e = govt_value*0.01 + mutation
        tds = govt_value*0.01 if govt_value>5_000_000 else 0
        total = stamp + e + tds

        st.write("## Govt Value Summary")
        st.write(f"Minimum Govt Value: ₹{govt_value:,.2f}")
        st.write(f"Total Govt Duty: ₹{total:,.2f}")

        if custom_flag and custom_value>0:
            stamp2 = custom_value * get_stampduty_rate(owner, custom_value)
            mutation2 = 1136 if (usage=="residential" and custom_value>5_000_000) else 1124
            e2 = custom_value*0.01 + mutation2
            tds2 = custom_value*0.01 if custom_value>5_000_000 else 0
            total2 = stamp2 + e2 + tds2
            st.write("---")
            st.write("### On Custom Value")
            st.write(f"Total Duty: ₹{total2:,.2f}")

    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------------------------
# HISTORY
# -------------------------------------------------

with tab_history:
    st.markdown("<div class='box'>", unsafe_allow_html=True)
    if not st.session_state.user_id:
        st.error("Login required")
    else:
        r = supabase.table("history").select("*") \
            .eq("user_id", st.session_state.user_id) \
            .order("created_at", desc=True).execute()
        df = pd.DataFrame(r.data or [])
        st.dataframe(df, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------------------------
# ABOUT
# -------------------------------------------------

with tab_about:
    st.markdown("<div class='box'>", unsafe_allow_html=True)
    st.write("""
    This tool calculates:
    - Circle Rate Value  
    - Construction Value  
    - Stamp Duty  
    - Mutation Fee  
    - E-Fees  
    - TDS  
    - DDA / CGHS Govt Value  
    """)
    st.write("Public Link:")
    st.code(APP_URL)
    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------------------------
# FOOTER
# -------------------------------------------------

st.markdown(
    f"<div class='footer'>© {date.today().year} Rishav Singh · Aggarwal Documents & Legal Consultants</div>",
    unsafe_allow_html=True
    )
