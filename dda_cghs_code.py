# dda_cghs_code.py

# ----------------- CONSTANTS -----------------

# Table 1.3 – minimum built-up rates up to four storeys
# Rs per sq. metre
AREA_CATEGORY_RATES = {
    "residential": {
        "upto_30": 50400,   # Up to 30 sq. m
        "30_50":   54480,   # Above 30 and up to 50
        "50_100":  66240,   # Above 50 and up to 100
        "above_100": 76200  # Above 100 sq. m
    },
    "commercial": {
        "upto_30": 57840,
        "30_50":   62520,
        "50_100":  75960,
        "above_100": 87360
    }
}

# Uniform rates when building has MORE than four storeys
UNIFORM_RATES_MORE_THAN_4 = {
    "residential": 87840,   # from your book: >4 storeys, >100 sqm example
    "commercial": 100800
}

# Gender-wise base stamp duty (when consideration <= 25L)
BASE_DUTY_RATES = {
    "female": 0.04,
    "joint":  0.05,
    "male":   0.06
}

EXTRA_DUTY_THRESHOLD = 2500000   # 25 lakh
TDS_THRESHOLD        = 5000000   # 50 lakh
TDS_RATE             = 0.01      # 1% TDS

CONVERSION_FACTOR_YD_TO_M = 0.8361  # 1 sq. yd = 0.8361 sq. m

# ----------------- HELPERS -----------------


def convert_sq_yards_to_sq_meters(area_sqyd: float) -> float:
    """Convert area from square yards to square metres."""
    return area_sqyd * CONVERSION_FACTOR_YD_TO_M


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


def calculate_minimum_value(plinth_area_sqm: float,
                            building_more_than_4_storeys: bool,
                            usage: str) -> float:
    """
    Minimum value = plinth area (sqm) * rate.

    usage: 'residential' or 'commercial'
    - If building has >4 storeys -> uniform rate from UNIFORM_RATES_MORE_THAN_4
    - Else -> category rate from AREA_CATEGORY_RATES[usage]
    """
    usage = usage.lower()
    if usage not in AREA_CATEGORY_RATES:
        raise ValueError("Usage must be 'residential' or 'commercial'.")

    if building_more_than_4_storeys:
        rate = UNIFORM_RATES_MORE_THAN_4[usage]
    else:
        category = determine_area_category(plinth_area_sqm)
        rate = AREA_CATEGORY_RATES[usage][category]

    return plinth_area_sqm * rate


def get_stamp_duty_rate(gender: str, consideration: float) -> float:
    """
    Base rate by gender, +1% if consideration > 25L.
    female : 4% / 5%
    joint  : 5% / 6%
    male   : 6% / 7%
    """
    gender = gender.lower()
    if gender not in BASE_DUTY_RATES:
        raise ValueError("Gender must be 'male', 'female' or 'joint'.")

    rate = BASE_DUTY_RATES[gender]
    if consideration > EXTRA_DUTY_THRESHOLD:
        rate += 0.01
    return rate


def calculate_stamp_duty(consideration: float, gender: str) -> float:
    rate = get_stamp_duty_rate(gender, consideration)
    return consideration * rate


def calculate_tds(consideration: float) -> float:
    return consideration * TDS_RATE if consideration > TDS_THRESHOLD else 0.0


def calculate_e_fees(consideration: float):
    """
    E/MCD fees = 1% of consideration + mutation.
    Mutation = 1,124 if <= 50L, else 1,136.
    Returns (total_e_fees, mutation_amount).
    """
    mutation = 1136 if consideration > 5000000 else 1124
    e_fee = consideration * 0.01 + mutation
    return e_fee, mutation


# ----------------- MAIN RUNNER -----------------


def run_dda_cghs():
    print("========== DDA / CGHS FLAT CALCULATOR ==========")

    try:
        area_sqyd = float(input("Enter plinth area (in sq. yards): ").strip())
    except ValueError:
        print("Invalid plinth area.")
        return

    if area_sqyd <= 0:
        print("Plinth area must be greater than 0.")
        return

    usage = input("Usage type (residential / commercial): ").strip().lower()
    if usage not in ("residential", "commercial"):
        print("Invalid usage type. Use 'residential' or 'commercial'.")
        return

    more_than_4 = input("Is the building having MORE than four storeys? (yes/no): ").strip().lower()
    building_more_than_4 = more_than_4 in ("yes", "y")

    gender = input("Buyer gender (male / female / joint): ").strip().lower()

    # convert to sq. metres for rate calculation
    plinth_area_sqm = convert_sq_yards_to_sq_meters(area_sqyd)

    # 1️⃣ Govt consideration (circle-value)
    try:
        govt_value = calculate_minimum_value(plinth_area_sqm, building_more_than_4, usage)
        duty_rate_govt = get_stamp_duty_rate(gender, govt_value)
        stamp_govt = calculate_stamp_duty(govt_value, gender)
        tds_govt = calculate_tds(govt_value)
        e_fees_govt, mutation_govt = calculate_e_fees(govt_value)
    except Exception as e:
        print(f"Error: {e}")
        return

    total_govt = stamp_govt + tds_govt + e_fees_govt

    print("\n------ GOVERNMENT (CIRCLE) VALUE ------")
    print(f"Usage type            : {usage.capitalize()}")
    print(f"Plinth area           : {area_sqyd:.2f} sq. yd = {plinth_area_sqm:.2f} sq. m")
    print(f"Minimum value         : ₹{govt_value:,.2f}")
    print(f"Stamp duty rate       : {duty_rate_govt*100:.2f}%")
    print(f"Stamp duty amount     : ₹{stamp_govt:,.2f}")
    if tds_govt > 0:
        print(f"TDS @1% (> ₹50L)      : ₹{tds_govt:,.2f}")
    else:
        print("TDS                   : Not applicable")
    print(f"E/MCD fees (1% + mutation ₹{mutation_govt}) : ₹{e_fees_govt:,.2f}")
    print(f"TOTAL govt liability  : ₹{total_govt:,.2f}")
    print("--------------------------------------")

    # 2️⃣ Custom consideration
    use_custom = input("\nCalculate on your own consideration value also? (yes/no): ").strip().lower()

    if use_custom in ("yes", "y"):
        try:
            custom_consideration = float(input("Enter your consideration value (₹): ").strip())
        except ValueError:
            print("Invalid consideration value.")
            return

        if custom_consideration <= 0:
            print("Consideration must be greater than 0.")
            return

        duty_rate_custom = get_stamp_duty_rate(gender, custom_consideration)
        stamp_custom = calculate_stamp_duty(custom_consideration, gender)
        tds_custom = calculate_tds(custom_consideration)
        e_fees_custom, mutation_custom = calculate_e_fees(custom_consideration)
        total_custom = stamp_custom + tds_custom + e_fees_custom

        print("\n------ CUSTOM CONSIDERATION ------")
        print(f"Consideration value   : ₹{custom_consideration:,.2f}")
        print(f"Stamp duty rate       : {duty_rate_custom*100:.2f}%")
        print(f"Stamp duty amount     : ₹{stamp_custom:,.2f}")
        if tds_custom > 0:
            print(f"TDS @1% (> ₹50L)      : ₹{tds_custom:,.2f}")
        else:
            print("TDS                   : Not applicable")
        print(f"E/MCD fees (1% + mutation ₹{mutation_custom}) : ₹{e_fees_custom:,.2f}")
        print(f"TOTAL liability       : ₹{total_custom:,.2f}")
        print("----------------------------------")

        if custom_consideration < govt_value:
            print("\n⚠ Note: Department normally uses the HIGHER of govt value and declared consideration.")

    print("\nCalculation finished.")


print("FILE LOADED SUCCESSFULLY")

if  __name__ == "__main__":
    run_dda_cghs()
