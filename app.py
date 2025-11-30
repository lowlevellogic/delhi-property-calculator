import streamlit as st
import math

# -----------------------------
# RESIDENTIAL DATA
# -----------------------------
circlerates_res = {
    "A": 774000, "B": 245520, "C": 159840, "D": 127680,
    "E": 70080, "F": 56640, "G": 46200, "H": 23280
}
construction_rates_res = {
    "A": 21960, "B": 17400, "C": 13920, "D": 11160,
    "E": 9360, "F": 8220, "G": 6960, "H": 3480
}

# -----------------------------
# COMMERCIAL DATA
# -----------------------------
circlerates_com = {
    "A": 774000 * 3, "B": 245520 * 3, "C": 159840 * 3, "D": 127680 * 3,
    "E": 70080 * 3, "F": 56640 * 3, "G": 46200 * 3, "H": 23280 * 3
}
construction_rates_com = {
    "A": 25200, "B": 19920, "C": 15960, "D": 12840,
    "E": 10800, "F": 9480, "G": 8040, "H": 3960
}

stampdutyrates = {"male": 0.06, "female": 0.04, "joint": 0.05}


# -----------------------------
# COMMON FUNCTIONS
# -----------------------------
def convert_sq_yards_to_sq_meters(sq_yards: float) -> float:
    """Convert sq. yards to sq. meters with 2 decimal places."""
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


# -----------------------------
# PAGE SETTINGS + STYLING
# -----------------------------
st.set_page_config(page_title="Delhi Property Calculator", layout="wide")

st.markdown(
    """
    <style>
        .stApp {
            background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
            color: #ffffff;
        }
        .title {
            font-size: 40px;
            font-weight: 900;
            text-align: center;
            color: #edf9ff;
        }
        .box {
            background: rgba(0, 0, 0, 0.45);
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 20px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<p class="title">🏠 Delhi Property Price Calculator</p>', unsafe_allow_html=True)
st.write("### Select property type and enter details below.")
st.write("---")

# -----------------------------
# PROPERTY TYPE
# -----------------------------
property_type = st.radio("Property Type", ["Residential", "Commercial"], horizontal=True)

if property_type == "Residential":
    circlerates = circlerates_res
    construction_rates = construction_rates_res
else:
    circlerates = circlerates_com
    construction_rates = construction_rates_com

# -----------------------------
# INPUT SECTION
# -----------------------------
st.markdown('<div class="box">', unsafe_allow_html=True)
st.write("## 📝 Property Details")

col1, col2 = st.columns(2)

with col1:
    land_area_yards = st.number_input(
        "Land Area (Sq. Yards)", value=50.0, min_value=1.0, step=1.0
    )
    category = st.selectbox("Property Category (A–H)", list(circlerates.keys()))

with col2:
    owner = st.selectbox("Ownership Type", ["male", "female", "joint"])
    include_const = st.radio("Includes Construction?", ["yes", "no"])

parking = st.radio("Parking Provided?", ["yes", "no"])

if include_const == "yes":
    st.write("### 🧱 Construction Details")
    col3, col4 = st.columns(2)
    with col3:
        total_storey = st.number_input("Total Storeys", value=1, min_value=1, step=1)
        user_storey = st.number_input("Storeys Buying", value=1, min_value=1, step=1)
    with col4:
        constructed_area = st.number_input(
            "Constructed Area (Sq. Yards)", value=50.0, min_value=1.0, step=1.0
        )
        year_built = st.number_input(
            "Year of Construction", value=2005, min_value=1900, max_value=2100, step=1
        )
else:
    total_storey = 1
    user_storey = 1
    constructed_area = 0.0
    year_built = 2000

st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------
# CUSTOM CONSIDERATION (INPUT)
# -----------------------------
st.markdown('<div class="box">', unsafe_allow_html=True)
st.write("## ✏️ Custom Consideration (Optional)")
custom_cons = st.number_input(
    "Enter your own consideration value (leave 0 to use auto-calculated):",
    value=0,
    min_value=0,
    step=1000,
)
st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------
# CALCULATE BUTTON
# -----------------------------
calc = st.button("Calculate Property Value")

if calc:
    # ---- LAND VALUE ----
    land_area_m = convert_sq_yards_to_sq_meters(land_area_yards)
    land_value_total = circlerates[category] * land_area_m
    storey_ratio = user_storey / total_storey
    land_value_user = land_value_total * storey_ratio

    # ---- CONSTRUCTION + PARKING ----
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

    # ---- FINAL CONSIDERATION (AUTO vs CUSTOM) ----
    if custom_cons > 0:
        final_consideration = float(custom_cons)
        used_text = "Custom consideration used"
    else:
        final_consideration = auto_consideration
        used_text = "Auto consideration used (no custom value entered)"

    # ---------------- AUTO SUMMARY ----------------
    st.markdown('<div class="box">', unsafe_allow_html=True)
    st.write("## 📊 Auto Calculation Summary")
    st.write(f"**Land Area (sq. meters):** {land_area_m:.2f}")
    st.write(f"**Your Land Value:** ₹{math.ceil(land_value_user):,}")
    st.write(f"**Construction Value:** ₹{math.ceil(construction_value):,}")
    st.write(f"**Parking Cost:** ₹{math.ceil(parking_cost):,}")
    st.write(f"**Auto Consideration (circle rate + construction):** "
             f"₹{math.ceil(auto_consideration):,}")
    st.markdown("</div>", unsafe_allow_html=True)

    # -------------- FINAL GOVT DUTY ----------------
    stamp_rate = get_stampduty_rate(owner, final_consideration)
    stamp_duty = final_consideration * stamp_rate

    # Mutation fees:
    #   Residential: 1124 (<=50L) / 1136 (>50L)
    #   Commercial: always 1124 (as per your original script)
    if property_type == "Residential":
        mutation = 1136 if final_consideration > 5_000_000 else 1124
    else:
        mutation = 1124

    e_fees = final_consideration * 0.01 + mutation
    tds = final_consideration * 0.01 if final_consideration > 5_000_000 else 0.0
    total_payable = stamp_duty + e_fees + tds

    st.markdown('<div class="box">', unsafe_allow_html=True)
    st.write("## 🧾 Final Govt. Duty Calculation")
    st.write(f"**Consideration used for duty ({used_text}):** "
             f"₹{math.ceil(final_consideration):,}")
    st.write(f"**Stamp Duty ({stamp_rate * 100:.3f}%):** "
             f"₹{math.ceil(stamp_duty):,}")
    st.write(f"**E-Fees (1% + mutation):** ₹{math.ceil(e_fees):,}")
    st.write(f"**TDS:** ₹{math.ceil(tds):,}")
    st.success(
        f"### Total Payable Govt. Duty: ₹{math.ceil(total_payable):,}"
    )
    st.markdown("</div>", unsafe_allow_html=True)
