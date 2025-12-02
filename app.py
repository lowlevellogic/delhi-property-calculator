import streamlit as st
import math
from datetime import datetime

# =========================
# CONFIG & CONSTANTS
# =========================

APP_URL = "https://delhi-property-calculator-lkdbpzkcuch6l8cgpehdsi.streamlit.app"

# Residential data
circlerates_res = {
    "A": 774000, "B": 245520, "C": 159840, "D": 127680,
    "E": 70080, "F": 56640, "G": 46200, "H": 23280
}
construction_rates_res = {
    "A": 21960, "B": 17400, "C": 13920, "D": 11160,
    "E": 9360, "F": 8220, "G": 6960, "H": 3480
}

# Commercial data
circlerates_com = {
    "A": 774000 * 3, "B": 245520 * 3, "C": 159840 * 3, "D": 127680 * 3,
    "E": 70080 * 3, "F": 56640 * 3, "G": 46200 * 3, "H": 23280 * 3
}
construction_rates_com = {
    "A": 25200, "B": 19920, "C": 15960, "D": 12840,
    "E": 10800, "F": 9480, "G": 8040, "H": 3960
}

stampdutyrates = {"male": 0.06, "female": 0.04, "joint": 0.05}

st.set_page_config(page_title="Delhi Property Price Calculator", layout="wide")

# =========================
# STYLING
# =========================

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

# =========================
# SESSION STATE INIT
# =========================

if "history" not in st.session_state:
    st.session_state.history = []  # list of dicts

if "last_result" not in st.session_state:
    st.session_state.last_result = None

if "last_result_tab" not in st.session_state:
    st.session_state.last_result_tab = None

# =========================
# COMMON FUNCTIONS
# =========================


def convert_sq_yards_to_sq_meters(sq_yards: float) -> float:
    """Convert sq. yards to sq. meters with 2 decimals."""
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
):
    # choose correct data
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

    # final consideration
    if custom_cons > 0:
        final_consideration = float(custom_cons)
        cons_source = "Custom consideration used"
    else:
        final_consideration = auto_consideration
        cons_source = "Auto consideration used (no custom value entered)"

    stamp_rate = get_stampduty_rate(owner, final_consideration)
    stamp_duty = final_consideration * stamp_rate

    # mutation logic
    if property_type == "Residential":
        mutation = 1136 if final_consideration > 5_000_000 else 1124
    else:
        mutation = 1124

    e_fees = final_consideration * 0.01 + mutation
    tds = final_consideration * 0.01 if final_consideration > 5_000_000 else 0.0
    total_payable = stamp_duty + e_fees + tds

    result = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "property_type": property_type,
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
    return result


def render_summary_block(res: dict):
    """Render the summary UI block under the calculation section."""
    st.markdown('<div class="box">', unsafe_allow_html=True)
    st.write("## 📊 Calculation Summary")

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
            f"**Custom Consideration Entered:** ₹{math.ceil(res['custom_consideration']):,}"
        )

    st.write(
        f"**Final Consideration Used ({res['cons_source']}):** "
        f"₹{math.ceil(res['final_consideration']):,}"
    )

    st.write("---")
    st.write("### Govt. Duty Calculation")
    st.write(
        f"**Stamp Duty ({res['stamp_rate']*100:.3f}%):** ₹{math.ceil(res['stamp_duty']):,}"
    )
    st.write(f"**Mutation Fees:** ₹{math.ceil(res['mutation']):,}")
    st.write(f"**E-Fees (1% + mutation):** ₹{math.ceil(res['e_fees']):,}")
    st.write(f"**TDS:** ₹{math.ceil(res['tds']):,}")
    st.success(
        f"**Total Payable Govt. Duty: ₹{math.ceil(res['total_payable']):,}**"
    )

    # Save to history button
    if st.button("💾 Save This Summary to History"):
        st.session_state.history.append(res)
        st.success("Summary saved to History tab.")

    st.markdown("</div>", unsafe_allow_html=True)


# =========================
# DDA / CGHS CONSTANTS & HELPERS
# =========================

# Table 1.3 – minimum built-up rates up to four storeys (Rs/sqm)
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

# Uniform rates when building has MORE than four storeys
UNIFORM_RATES_MORE_THAN_4 = {
    "residential": 87840,
    "commercial": 100800,
}


def determine_area_category(plinth_area_sqm: float) -> str:
    """Return the plinth-area category key."""
    if plinth_area_sqm <= 30:
        return "upto_30"
    elif plinth_area_sqm <= 50:
        return "30_50"
    elif plinth_area_sqm <= 100:
        return "50_100"
    else:
        return "above_100"


def dda_minimum_value(plinth_area_sqm: float,
                      building_more_than_4_storeys: bool,
                      usage: str) -> tuple[float, float]:
    """
    Returns (rate_per_sqm, minimum_value).
    usage: 'residential' or 'commercial'
    """
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


def dda_e_fees_and_tds(consideration: float, usage: str):
    """Reuse same gov logic as main calculator."""
    stamp_rate = get_stampduty_rate("male", consideration)  # owner type handled elsewhere
    # we won't use this stamp_rate here, just keeping pattern similar


# =========================
# HEADER WITH LOGO + BRAND
# =========================

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

# =========================
# TABS LAYOUT
# =========================

tab_home, tab_res, tab_com, tab_dda, tab_history, tab_about = st.tabs(
    ["🏠 Home", "📄 Residential", "🏬 Commercial", "🏢 DDA/CGHS Flats", "📚 History", "ℹ️ About"]
)

# -------------------------
# HOME TAB
# -------------------------
with tab_home:
    st.markdown(
        """
        <div class="box">
        <h3>Welcome to the Delhi Property Price Calculator</h3>
        <p>
        This tool helps you quickly estimate the value of Residential and Commercial
        properties in Delhi based on circle rates, construction, parking, stamp duty,
        e-fees and TDS.
        </p>
        <ul>
            <li>Use the <b>Residential</b> or <b>Commercial</b> tab to calculate.</li>
            <li>The <b>DDA/CGHS Flats</b> tab uses built-up rates based on plinth area and storeys.</li>
            <li>After calculation, summary appears below the button.</li>
            <li>Click <b>"Save This Summary to History"</b> to store it for later.</li>
            <li>See all saved calculations in the <b>History</b> tab.</li>
        </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

# -------------------------
# RESIDENTIAL TAB
# -------------------------
with tab_res:
    st.markdown('<div class="box">', unsafe_allow_html=True)
    st.subheader("Residential Property Calculation")

    col1, col2 = st.columns(2)
    with col1:
        r_land_area_yards = st.number_input(
            "Land Area (Sq. Yards)",
            value=50.0,
            min_value=1.0,
            step=1.0,
            key="r_land_area",
        )
        r_category = st.selectbox(
            "Property Category (A–H)", list(circlerates_res.keys()), key="r_category"
        )
        r_total_storey = st.number_input(
            "Total Storeys", value=1, min_value=1, step=1, key="r_total_storey"
        )
        r_user_storey = st.number_input(
            "Storeys Buying", value=1, min_value=1, step=1, key="r_user_storey"
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
        result = run_calculation(
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
        )
        st.session_state.last_result = result
        st.session_state.last_result_tab = "Residential"
        st.success("Residential property calculation completed.")

    # Show summary under calculation if last_result belongs to Residential
    if (
        st.session_state.last_result is not None
        and st.session_state.last_result_tab == "Residential"
    ):
        render_summary_block(st.session_state.last_result)

    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# COMMERCIAL TAB
# -------------------------
with tab_com:
    st.markdown('<div class="box">', unsafe_allow_html=True)
    st.subheader("Commercial Property Calculation")

    col1, col2 = st.columns(2)
    with col1:
        c_land_area_yards = st.number_input(
            "Land Area (Sq. Yards)",
            value=50.0,
            min_value=1.0,
            step=1.0,
            key="c_land_area",
        )
        c_category = st.selectbox(
            "Property Category (A–H)", list(circlerates_com.keys()), key="c_category"
        )
        c_total_storey = st.number_input(
            "Total Storeys", value=1, min_value=1, step=1, key="c_total_storey"
        )
        c_user_storey = st.number_input(
            "Storeys Buying", value=1, min_value=1, step=1, key="c_user_storey"
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
        result = run_calculation(
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
        )
        st.session_state.last_result = result
        st.session_state.last_result_tab = "Commercial"
        st.success("Commercial property calculation completed.")

    # Show summary under calculation if last_result belongs to Commercial
    if (
        st.session_state.last_result is not None
        and st.session_state.last_result_tab == "Commercial"
    ):
        render_summary_block(st.session_state.last_result)

    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# DDA / CGHS TAB
# -------------------------
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

        # Govt value duties
        duty_rate_govt = get_stampduty_rate(dda_owner, govt_value)
        stamp_govt = govt_value * duty_rate_govt
        # mutation rules same as main calculator
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
            st.write("**Storey Rule:** Uniform rate applied (building has more than 4 storeys)")
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

        # Custom consideration block
        if dda_calc_custom and dda_custom_cons > 0:
            duty_rate_custom = get_stampduty_rate(dda_owner, dda_custom_cons)
            stamp_custom = dda_custom_cons * duty_rate_custom
            if usage_key == "residential":
                mutation_custom = 1136 if dda_custom_cons > 5_000_000 else 1124
            else:
                mutation_custom = 1124
            e_fees_custom = dda_custom_cons * 0.01 + mutation_custom
            tds_custom = (
                dda_custom_cons * 0.01 if dda_custom_cons > 5_000_000 else 0.0
            )
            total_custom = stamp_custom + e_fees_custom + tds_custom

            st.write("---")
            st.write("## 🔹 Custom Consideration Calculation")
            st.write(f"**Consideration Value:** ₹{dda_custom_cons:,.2f}")
            st.write(f"**Stamp Duty Rate:** {duty_rate_custom*100:.2f}%")
            st.write(f"**Stamp Duty Amount:** ₹{math.ceil(stamp_custom):,}")
            st.write(f"**Mutation Fees:** ₹{mutation_custom:,}")
            st.write(f"**E-Fees (1% + mutation):** ₹{math.ceil(e_fees_custom):,}")
            if tds_custom > 0:
                st.write(f"**TDS (1% > ₹50L):** ₹{math.ceil(tds_custom):,}")
            else:
                st.write("**TDS (1% > ₹50L):** Not applicable")
            st.success(
                f"**Total Govt Liability on Custom Consideration: ₹{math.ceil(total_custom):,}**"
            )

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# HISTORY TAB
# -------------------------
with tab_history:
    st.markdown('<div class="box">', unsafe_allow_html=True)
    st.subheader("Saved Summaries (History)")

    if not st.session_state.history:
        st.info(
            "No saved summaries yet. Use Residential or Commercial tab, calculate and click 'Save This Summary to History'."
        )
    else:
        rows = []
        for h in st.session_state.history:
            rows.append(
                {
                    "Time": h["timestamp"],
                    "Type": h["property_type"],
                    "Category": h["category"],
                    "Consideration Used (₹)": math.ceil(h["final_consideration"]),
                    "Stamp Duty (₹)": math.ceil(h["stamp_duty"]),
                    "E-Fees (₹)": math.ceil(h["e_fees"]),
                    "TDS (₹)": math.ceil(h["tds"]),
                    "Total Govt Duty (₹)": math.ceil(h["total_payable"]),
                }
            )
        st.dataframe(rows, use_container_width=True)
        if st.button("Clear History"):
            st.session_state.history = []
            st.success("History cleared for this session.")

    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# ABOUT / BRANDING / SHARE
# -------------------------
with tab_about:
    st.markdown('<div class="box">', unsafe_allow_html=True)
    st.subheader("About Aggarwal Documents & Legal Consultants")

    st.write(
        """
        This calculator is designed to help estimate Delhi property values and government
        duty amounts in a quick and easy way.

        **Aggarwal Documents & Legal Consultants**  
        Providing assistance in:
        - Property Documentation  
        - Sale Deeds & Agreements  
        - Registration & Legal Consultancy  
        """
    )

    st.write("---")
    st.write("### 🔗 Share this App")

    st.write("You can share this calculator with others:")

    # Copy Link button (JS)
    st.markdown(
        f"""
        <button onclick="navigator.clipboard.writeText('{APP_URL}'); 
                         alert('App link copied to clipboard!');"
                style="padding:8px 16px; border-radius:8px; border:none;
                       background-color:#00c853; color:white; margin-right:10px;
                       cursor:pointer;">
            📋 Copy App Link
        </button>
        """,
        unsafe_allow_html=True,
    )

    # WhatsApp share button
    wa_text = (
        "Check this Delhi Property Price Calculator by Aggarwal Documents & Legal Consultants: "
    )
    wa_url = "https://wa.me/?text=" + (wa_text + APP_URL).replace(" ", "%20")
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

# -------------------------
# FOOTER
# -------------------------
st.markdown(
    '<div class="footer">Created by <b>Rishav Singh</b> · Aggarwal Documents &amp; Legal Consultants</div>',
    unsafe_allow_html=True,
)
