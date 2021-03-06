import os.path
import uuid
from datetime import date, datetime
import xml.etree.ElementTree as ET

# define default currency and all involved currencies, with their sub-units
DEFAULT_CURRENCY = 'BGN'
CURRENCY_UNITS = {'BGN': '100', 'USD': '100', 'EUR': '100', 'JPY': '1'}
ACE_CURRENCY_CODES = {'155': 'BGN', '43': 'EUR', '63': 'JPY', '140': 'USD'}
ACE_INCOME_CATEGORY_IDS = ('10', '51')
ACE_OPENING_BALANCE_CATEGORY_IDS = ('136',)
OPENING_BALANCE_DAY = date(2000, 1, 1)
FX_RATES_FILENAME = 'fxrates.xml'
DEBUG = False

fx_rates_map = {}  # key is (currency, day); value is fx-rate, a float


def get_default_fx_rate(currency):
    """ Returns the default fx-rate for the given currency, expressed in DEFAULT_CURRENCY. BGN-specific values"""
    if currency == DEFAULT_CURRENCY:
        return 1.0
    if currency == 'EUR':
        return 1.95583
    if currency == 'USD':
        return 1.5
    if currency == 'JPY':
        return 0.015
    return 1.0


def get_fx_rate(currency, day):
    """ Looks up a cached fx-rate for start-of-month. Returns a default fx-rate is not found """
    if currency == DEFAULT_CURRENCY:
        return 1.0

    # check for a cached SOM FX
    start_of_month = day.replace(day=1)
    cached_fx = fx_rates_map.get((currency, start_of_month))
    if cached_fx is not None:
        return cached_fx

    return get_default_fx_rate(currency)


def init_fx_rates():
    """ Populates the fx-rates cache with default values and with values from fxrates.xml"""
    if len(fx_rates_map) != 0:
        return  # already initialized

    # default fx rates
    for currency in sorted(CURRENCY_UNITS.keys()):
        if currency != DEFAULT_CURRENCY:
            fx_rates_map[(currency, OPENING_BALANCE_DAY)] = get_default_fx_rate(currency)

    # any fx rates from a file?
    if os.path.exists(FX_RATES_FILENAME):
        for fx_element in ET.parse(FX_RATES_FILENAME).findall('.//rate'):
            currency = fx_element.get('currency')
            fx_rate = fx_element.get('fx')
            day = datetime.strptime(fx_element.get('day'), '%Y-%m-%d').date()
            fx_rates_map[(currency, day)] = float(fx_rate)


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


def next_id():
    return uuid.uuid4().get_hex()
