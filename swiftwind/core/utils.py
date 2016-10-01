from decimal import Decimal


# All of these functions should be considered for removal
# unless used following the django-hordak refactoring

def ratio_split(in_value, ratios, precision=2):
    ratio_total = sum(ratios)
    divided_value = in_value / ratio_total
    values = []
    for ratio in ratios:
        value = divided_value * ratio
        values.append(value)

    # Now round the values, keeping track of the bits we cut off
    rounded = [v.quantize(Decimal('0.01')) for v in values]
    remainders = [v - rounded[i] for i, v in enumerate(values)]
    remainder = sum(remainders)
    # Give the last person the (positive or negative) remainder
    rounded[-1] = (rounded[-1] + remainder).quantize(Decimal('0.01'))

    return rounded
