"""Pure decimal-input comparator; exact rational cross-multiplication at boundaries."""

from decimal import Decimal, localcontext
from fractions import Fraction

from app.domain.measurements import UNITS, CompareInput, SpecInput

# Canonical physical units: C, Pa, V, ohm. All scale/offset constants exact.
SCALE = {
    "C": (Fraction(1), Fraction(0)),
    "F": (Fraction(5, 9), Fraction(-160, 9)),
    "Pa": (Fraction(1), Fraction(0)),
    "kPa": (Fraction(1000), Fraction(0)),
    "bar": (Fraction(100000), Fraction(0)),
    "V": (Fraction(1), Fraction(0)),
    "mV": (Fraction(1, 1000), Fraction(0)),
    "ohm": (Fraction(1), Fraction(0)),
    "kohm": (Fraction(1000), Fraction(0)),
}


class MeasurementComparator:
    @staticmethod
    def compare(spec, measurement):
        spec = SpecInput.model_validate(spec).model_dump(mode="json")
        measurement = CompareInput.model_validate(measurement)
        original = measurement.model_dump(mode="json")
        out = dict(
            outcome=None,
            input=original,
            converted=None,
            converted_exact=None,
            unit=spec["unit"],
            bounds={k: spec[k] for k in ["lower", "upper", "lower_inclusive", "upper_inclusive"]},
        )
        if measurement.value is None:
            out["outcome"] = "value_missing"
            return out
        if measurement.quantity != spec["quantity"]:
            out["outcome"] = "quantity_mismatch"
            return out
        if (
            measurement.unit not in UNITS[measurement.quantity]
            or spec["unit"] not in UNITS[spec["quantity"]]
        ):
            out["outcome"] = "unit_mismatch"
            return out
        missing = sorted(set(spec["conditions"]) - set(measurement.conditions))
        if missing:
            out.update(outcome="conditions_missing", missing=missing)
            return out
        if any(measurement.conditions[k] != v for k, v in spec["conditions"].items()):
            out["outcome"] = "conditions_mismatch"
            return out
        scale, offset = SCALE[measurement.unit]
        target_scale, target_offset = SCALE[spec["unit"]]
        exact = (
            Fraction(Decimal(measurement.value)) * scale + offset - target_offset
        ) / target_scale
        with localcontext() as ctx:
            ctx.prec = 100
            value = Decimal(exact.numerator) / Decimal(exact.denominator)
        out.update(converted=str(value), converted_exact=Fraction(value) == exact)
        low = Fraction(Decimal(spec["lower"])) if spec["lower"] is not None else None
        high = Fraction(Decimal(spec["upper"])) if spec["upper"] is not None else None
        inside = (low is None or exact > low or (exact == low and spec["lower_inclusive"])) and (
            high is None or exact < high or (exact == high and spec["upper_inclusive"])
        )
        out["outcome"] = "within_range" if inside else "out_of_range"
        return out
