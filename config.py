from datetime import date

# define default currency and all involved currencies, with their sub-units
DEFAULT_CURRENCY = 'BGN'
CURRENCY_UNITS = {'BGN': '100', 'USD': '100', 'EUR': '100', 'JPY': '1'}
OPENING_BALANCE_DAY = date(2000, 1, 1)
DEBUG = False


def indent(elem, level=0):
    i = "\n" + level * "    "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "    "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent(elem, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


def concat(first, second, spacer=''):
    if first is not None:
        result = first
        if second is not None:
            result += spacer + second
        return result
    else:
        return second