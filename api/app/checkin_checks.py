"""Format and logic checks that the API adds to a manual check-in.

The API is the trust boundary, so it runs these checks after A's contract
validation (validate_manual_check_in) and before the assessment. They reject
only values that cannot be a real reading by definition:

- every measurement is a plain decimal number, with up to 4 digits before the
  decimal point and up to 3 after: no sign, exponent ("1e3") or spaces;
- heart rate, breathing rate and both blood pressures are above 0;
- systolic pressure (the highest pressure of a heartbeat) is above diastolic
  pressure (the lowest);
- the sleep reported in a daily check-in is at most 24 hours.

These are NOT medical limits. Physiological ranges, such as the highest
plausible heart rate, need a cited source in catalogue/indicators.yaml and are
still open (AGENTS.md, section 4). So a value such as 300 bpm passes these
checks and is compared with personal history as usual.
"""

import re
from collections.abc import Mapping
from decimal import Decimal

PLAIN_NUMBER = re.compile(r"[0-9]{1,4}(?:\.[0-9]{1,3})?")
ABOVE_ZERO = ("heart_rate", "respiratory_rate", "systolic_bp", "diastolic_bp")
HOURS_IN_A_DAY = Decimal(24)


def check_readings(raw: Mapping[str, object], indicators: Mapping[str, object]) -> None:
    """Raise ValueError naming the first reading that cannot be real.

    raw: the indicators exactly as the client sent them, to see how each number
    was written. indicators: the same indicators after validate_manual_check_in,
    which already guarantees their structure, units and nonnegative values.
    """
    for name, item in raw.items():
        if name == "mood" or item is None:
            continue
        if not PLAIN_NUMBER.fullmatch(str(item["value"])):
            raise ValueError(
                f"{name}: write the value as a plain number with up to 4 digits before "
                "the decimal point and 3 after, for example 72 or 72.5"
            )
    values = {name: Decimal(item["value"]) for name, item in indicators.items() if name != "mood"}
    for name in ABOVE_ZERO:
        if values[name] <= 0:
            raise ValueError(f"{name}: a measured value must be above 0")
    if values["systolic_bp"] <= values["diastolic_bp"]:
        raise ValueError("systolic_bp must be greater than diastolic_bp")
    if values.get("sleep_duration", Decimal(0)) > HOURS_IN_A_DAY:
        raise ValueError("sleep_duration: a daily check-in cannot report more than 24 hours")
