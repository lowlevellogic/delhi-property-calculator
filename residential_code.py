import math
import os

# Circle rates 
circlerates = {
    "A": 774000,
    "B": 245520,
    "C": 159840,
    "D": 127680,
    "E": 70080,
    "F": 56640,
    "G": 46200,
    "H": 23280
}

# Construction rates 
construction_rates = {
    "A": 21960,
    "B": 17400,
    "C": 13920,
    "D": 11160,
    "E": 9360,
    "F": 8220,
    "G": 6960,
    "H": 3480
}

# Base stamp duty rates
stampdutyrates = {
    "male": 0.06,
    "female": 0.04,
    "joint": 0.05
}

def calculate_property_value(area, category):
    rate = circlerates.get(category.upper())
    return rate * area if rate else None

def calculate_construction_value(constructed_area, category):
    rate = construction_rates.get(category.upper())
    return constructed_area * rate if rate else None

def get_stampduty(ownertype, total_consideration):
    base_rate = stampdutyrates.get(ownertype.lower())
    if base_rate is None:
        return None
    return base_rate + 0.01 if total_consideration > 2500000 else base_rate

def calculate_stampduty(stampable_value, ownertype, total_consideration):
    duty_rate = get_stampduty(ownertype, total_consideration)
    return stampable_value * duty_rate if duty_rate else None

def calculate_efees(total_consideration):
    return total_consideration * 0.01

def calculate_tds(total_consideration):
    return total_consideration * 0.01 if total_consideration > 5000000 else 0

def age(year_built):
    if year_built < 1960:
        return 0.5
    elif 1960 <= year_built <= 1969:
        return 0.6
    elif 1970 <= year_built <= 1979:
        return 0.7
    elif 1980 <= year_built <= 1989:
        return 0.8
    elif 1990 <= year_built <= 2000:
        return 0.9
    else:
        return 1.0

def convert_sq_yards_to_sq_meters(sq_yards):
    result = sq_yards * 0.8361
    return math.floor(result * 100) / 100

def run_residential():
    print("Delhi Residential Property Calculator!".center(80))
    try:
        area_1 = float(input("Enter Land Area (in Sq. Yards): "))
        area = convert_sq_yards_to_sq_meters(area_1)

        category = input("Enter property category (A to H): ").upper()
        owner_type = input("Enter Property Buying type (male/female/joint): ").lower()
        add_construction = input("Property includes construction? (yes/no): ").lower()
        parking_input = input("Is parking provided? (yes/no): ").lower()

        total_storey = 1
        user_storey = 1

        if add_construction == "yes":
            total_storey = int(input("Enter Total No. of Storeys: "))
            user_storey = int(input("Enter No. of Storeys buying: "))

        total_land_value = calculate_property_value(area, category)
        if total_land_value is None:
            print("Invalid Category.")
            return 0

        storey_ratio = user_storey / total_storey if total_storey > 1 else 1.0
        user_land_value = total_land_value * storey_ratio

        print("sq meter:", area)

        # Construction
        construction_value = 0
        construction_rate_used = 0
        age_multiplier = 1.0

        if add_construction == "yes":
            constructed_area = float(input("Enter constructed area (in sq. yards): "))
            constructed_area_m = convert_sq_yards_to_sq_meters(constructed_area)
            year_built = int(input("Enter year of Construction: "))
            age_multiplier = age(year_built)

            base_construction_value = calculate_construction_value(constructed_area_m, category)
            if base_construction_value is None:
                print("Invalid category for construction.")
                return 0

            construction_value = base_construction_value * age_multiplier * user_storey
            construction_rate_used = construction_rates[category.upper()]

            print(f"Base Construction Value: Rs.{base_construction_value:,.2f}")
            print(f"Age Multiplier Applied: {age_multiplier}")
            print(f"Depreciated Construction Value: Rs.{construction_value:,.2f}")

        parking_cost = 0
        if parking_input == "yes" and construction_rate_used > 0:
            parking_cost = (area * construction_rate_used * user_storey) / total_storey

        user_construction_value = construction_value + parking_cost
        total_user_value = user_land_value + user_construction_value
        total_consideration = total_user_value

        print(f"\nCalculated Total Consideration: Rs.{math.ceil(total_consideration):,}")

        custom_consid = input("Own Consideration Value? (yes/no): ").lower()
        if custom_consid == "yes":
            try:
                user_defined_consid = int(input("Enter your own consideration value (in Rs.): "))
                total_consideration = user_defined_consid    
            except ValueError:
                print("Invalid consideration value entered.")

        if user_storey > total_storey or user_storey <= 0:
            print("Invalid no. of Storeys.")
            return 0

        stamp_duty = calculate_stampduty(total_consideration, owner_type, total_consideration)
        stamp_duty_rate_used = get_stampduty(owner_type, total_consideration)
        if total_consideration > 5000000:
            mutation_fees = 1136
        else:
            mutation_fees = 1124
        e_fees = calculate_efees(total_consideration) + mutation_fees
        tds = calculate_tds(total_consideration)
        total_payable = stamp_duty + e_fees
        total_payable_tds = stamp_duty + e_fees + tds
        os.system('cls')

        print("\n--- Property Calculation Summary ---")
        print(f"Category: {category}")
        print(f"Land Area: {area_1} sq. yards")
        print(f"Land Value: Rs.{math.ceil(user_land_value):,}")
        print(f"Total Consideration: Rs.{math.ceil(total_consideration):,}")
        print(f"Total Storeys: {total_storey}, You’re Buying: {user_storey}")
        print(f"Your Share: {storey_ratio * 100:.2f}%")
        print(f"Your Land Value: Rs.{math.ceil(user_land_value):,}")
        if parking_input =="yes":
            print(f"Your Construction Value (with parking): Rs.{math.ceil(user_construction_value):,}")
        else:
            print(f"Your Construction Value : Rs.{math.ceil(user_construction_value):,}")
        print(f"Stamp Duty Rate: {stamp_duty_rate_used * 100:.2f}%")
        print(f"Stamp Duty: Rs.{math.ceil(stamp_duty):,}")
        print(f"E-Fees: Rs.{math.ceil(e_fees):,}")
        if total_consideration > 5000000:
            print(f"TDS Applicable (1% over ₹50L): Rs.{math.ceil(tds):,}")
            print(f"Total Payable Govt. Duty (Stamp Duty + E-Fees + TDS): Rs.{math.ceil(total_payable_tds):,}")
        else:
            print(f"TDS Not Applicable")
            print(f"Total Payable Govt. Duty (Stamp Duty + E-Fees): Rs.{math.ceil(total_payable):,}")
        print(f"Parking Cost: Rs.{math.ceil(parking_cost):,}")

        return total_consideration

    except ValueError:
        print("Please enter valid inputs.")
        return 0

if __name__ == "__main__":
    run_residential()
