import xml.etree.ElementTree as ET
import uuid
from fractions import Fraction
import os.path
from datetime import date, datetime

# define default currency and all involved currencies, with their sub-units
import fxscraper

DEFAULT_CURRENCY = 'BGN'
CURRENCY_UNITS = {'BGN': '100', 'USD': '100', 'EUR': '100', 'JPY': '1'}
OPENING_BALANCE_DAY = date(2000, 1, 1)
DEBUG = False


def next_id():
    return uuid.uuid4().get_hex()


root_account_id = next_id()
opening_balances_accounts_ids = {}
trading_currency_account_ids = {}
placeholder = {'placeholder': 'true'}
fx_rates_map = {}  # key is (currency, day); value is fx-rate, a float


class GnuSplit:
    def __init__(self, account_id, amount, currency):
        self.account_id = account_id
        self.amount = amount
        self.currency = currency


# 1 of 'currency' = 'rate' of 'default_currency'
class GnuFxRate:
    def __init__(self, currency, rate, day):
        self.currency = currency
        self.rate = rate
        self.day = day


# BGN-specific
def get_fx_rate(currency, day):
    if currency == DEFAULT_CURRENCY:
        return 1.0
    if currency == 'EUR':
        return 1.95583

    # check for a cached SOM FX
    start_of_month = day.replace(day=1)
    cached_fx = fx_rates_map[(currency, start_of_month)]
    if cached_fx is not None:
        return cached_fx

    # final fallback
    if currency == 'USD':
        return 1.5
    if currency == 'JPY':
        return 0.015


def write_currency_commodity(element, currency):
    cmd_space = ET.SubElement(element, 'cmdty:space')
    cmd_space.text = 'ISO4217'
    cmd_space = ET.SubElement(element, 'cmdty:id')
    cmd_space.text = currency


def write_commodities(xml_root):
    for currency in sorted(CURRENCY_UNITS.keys()):
        commodity = ET.SubElement(xml_root, 'gnc:commodity', {'version': "2.0.0"})
        write_currency_commodity(commodity, currency)
        ET.SubElement(commodity, 'cmdty:get_quotes')
        cmd_src = ET.SubElement(commodity, 'cmdty:quote_source')
        cmd_src.text = 'currency'
        ET.SubElement(commodity, 'cmdty:quote_tz')


def write_root_account(xml_root):
    write_account(xml_root, 'Root Account', root_account_id, 'ROOT', None, DEFAULT_CURRENCY, None)


def write_opening_balances(xml_root):
    equity_account_id = next_id()
    opening_balances_account_id = next_id()

    # create Equity and Equity:Opening Balances accounts
    write_account(xml_root, 'Equity', equity_account_id, 'EQUITY', None, DEFAULT_CURRENCY, root_account_id, placeholder)
    write_account(xml_root, 'Opening Balances', opening_balances_account_id, 'EQUITY', None, DEFAULT_CURRENCY,
                  equity_account_id, placeholder)

    # create sub-accounts for each specified currency
    for currency in sorted(CURRENCY_UNITS.keys()):
        # generate and map the ID
        account_id = next_id()
        opening_balances_accounts_ids[currency] = account_id

        write_account(xml_root, currency, account_id, 'EQUITY', None, currency, opening_balances_account_id)


def write_trading_accounts(xml_root):
    trading_account_id = next_id()
    trading_currency_account_id = next_id()

    # create Trading and Trading:CURRENCY accounts
    write_account(xml_root, 'Trading', trading_account_id, 'TRADING', None, DEFAULT_CURRENCY, root_account_id,
                  placeholder)
    write_account(xml_root, 'CURRENCY', trading_currency_account_id, 'TRADING', None, DEFAULT_CURRENCY,
                  trading_account_id, placeholder)

    # create sub-accounts for each specified currency
    for currency in sorted(CURRENCY_UNITS.keys()):
        # generate and map the ID
        account_id = next_id()
        trading_currency_account_ids[currency] = account_id

        write_account(xml_root, currency, account_id, 'TRADING', None, currency, trading_currency_account_id)


def add_currency_child(parent_element, currency, child_tag_name):
    act_commodity = ET.SubElement(parent_element, child_tag_name)
    write_currency_commodity(act_commodity, currency)


def add_timestamp(parent_element, day, child_tag_name):
    date_outer = ET.SubElement(parent_element, child_tag_name)
    date_inner = ET.SubElement(date_outer, 'ts:date')
    date_inner.text = str(day) + ' 00:00:00 +0200'


def write_account(xml_root, name, account_id, account_type, account_code, currency, parent_id, slots=None):
    acc = ET.SubElement(xml_root, 'gnc:account', {'version': "2.0.0"})
    act_name = ET.SubElement(acc, 'act:name')
    act_name.text = name
    act_id = ET.SubElement(acc, 'act:id', {'type': "guid"})
    act_id.text = account_id
    act_type = ET.SubElement(acc, 'act:type')
    act_type.text = account_type
    if account_code is not None:
        act_code = ET.SubElement(acc, 'act:code')
        act_code.text = account_code
    add_currency_child(acc, currency, 'act:commodity')
    act_scu = ET.SubElement(acc, 'act:commodity-scu')
    act_scu.text = CURRENCY_UNITS[currency]
    if slots is not None:
        act_slots = ET.SubElement(acc, 'act:slots')
        for key in slots:
            act_slot = ET.SubElement(act_slots, 'slot')
            act_slot_key = ET.SubElement(act_slot, 'slot:key')
            act_slot_key.text = key
            act_slot_value = ET.SubElement(act_slot, 'slot:value', {'type': "string"})
            act_slot_value.text = slots[key]
    if parent_id is not None:
        act_parent_id = ET.SubElement(acc, 'act:parent', {'type': "guid"})
        act_parent_id.text = parent_id


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


def build_comment(account):
    debug_info = 'AceID=' + account.ace_id + ' Balance=' + account.balance if DEBUG else None
    return concat(account.comment, debug_info, '\n')


def write_ace_accounts(xml_root, account_groups, accounts):
    # create a top-level account for each AceMoney group
    for group in account_groups:
        slots = placeholder.copy()
        if DEBUG:
            slots['notes'] = 'AceGroupID=' + group.ace_id
        write_account(xml_root, group.name, group.gnu_id, 'BANK', None, DEFAULT_CURRENCY, root_account_id, slots)

    # create an account for each AceMoney account
    for account in accounts:
        slots = {}
        comment = build_comment(account)
        if comment is not None and comment != '':
            slots['notes'] = comment
        if account.hidden:
            slots['hidden'] = 'true'
        write_account(xml_root, account.name, account.gnu_id, 'BANK', account.number, account.currency,
                      account.group.gnu_id, slots)

    # setup the initial balance transaction for each AceMoney account
    for account in accounts:
        if account.balance != '0':
            split_src = GnuSplit(account.gnu_id, account.balance, account.currency)
            split_dst = GnuSplit(opening_balances_accounts_ids[account.currency], account.balance, account.currency)
            write_transaction(xml_root, account.currency, OPENING_BALANCE_DAY, None, None, True, split_src, split_dst)


def add_split(splits, value, quantity, account, reconciled):
    split = ET.SubElement(splits, 'trn:split')

    split_id = ET.SubElement(split, 'split:id', {'type': "guid"})
    split_id.text = next_id()
    split_rec = ET.SubElement(split, 'split:reconciled-state')
    split_rec.text = 'y' if reconciled else 'n'
    split_value = ET.SubElement(split, 'split:value')
    split_value.text = value
    split_quantity = ET.SubElement(split, 'split:quantity')
    split_quantity.text = quantity
    split_acc = ET.SubElement(split, 'split:account', {'type': "guid"})
    split_acc.text = account


def write_transaction(xml_root, currency, day, description, num, reconciled, split_src, split_dst):
    tran = ET.SubElement(xml_root, 'gnc:transaction', {'version': "2.0.0"})
    tran_id = ET.SubElement(tran, 'trn:id', {'type': "guid"})
    tran_id.text = next_id()
    add_currency_child(tran, currency, 'trn:currency')
    add_timestamp(tran, day, 'trn:date-posted')
    add_timestamp(tran, day, 'trn:date-entered')

    tran_desc = ET.SubElement(tran, 'trn:description')
    if description is not None:
        tran_desc.text = description
    tran_num = ET.SubElement(tran, 'trn:num')
    # Note: 'num' field is the secondary sort criteria, after the transaction date
    if num is not None:
        tran_num.text = num
    tran_slots = ET.SubElement(tran, 'trn:slots')
    tran_slot = ET.SubElement(tran_slots, 'slot')
    tran_slot_key = ET.SubElement(tran_slot, 'slot:key')
    tran_slot_key.text = 'date-posted'
    tran_slot_value = ET.SubElement(tran_slot, 'slot:value', {'type': "gdate"})
    gdate = ET.SubElement(tran_slot_value, 'gdate')
    gdate.text = str(day)

    multiplier_src = CURRENCY_UNITS[split_src.currency]
    amount_src = int(round(float(split_src.amount) * float(multiplier_src)))

    multiplier_dst = CURRENCY_UNITS[split_dst.currency]
    amount_dst = int(round(float(split_dst.amount) * float(multiplier_dst)))

    tran_splits = ET.SubElement(tran, 'trn:splits')

    value_src_pos = str(amount_src) + '/' + multiplier_src
    value_src_neg = str(-amount_src) + '/' + multiplier_src
    value_dst_pos = str(amount_dst) + '/' + multiplier_dst
    value_dst_neg = str(-amount_dst) + '/' + multiplier_dst
    add_split(tran_splits, value_src_pos, value_src_pos, split_src.account_id, reconciled)
    add_split(tran_splits, value_src_neg, value_dst_neg, split_dst.account_id, reconciled)

    if split_src.currency != split_dst.currency:
        # generate trading account entries
        add_split(tran_splits, value_src_neg, value_src_neg, trading_currency_account_ids[split_src.currency],
                  reconciled)
        add_split(tran_splits, value_src_pos, value_dst_pos, trading_currency_account_ids[split_dst.currency],
                  reconciled)


def write_ace_categories(xml_root, categories):
    expenses_account_id = next_id()
    write_account(xml_root, 'Expense', expenses_account_id, 'EXPENSE', None, DEFAULT_CURRENCY, root_account_id,
                  placeholder)

    for category in categories:
        if category.parent is None:
            write_account(xml_root, category.name, category.gnu_id, 'EXPENSE', None, DEFAULT_CURRENCY,
                          expenses_account_id)

    for category in categories:
        if category.parent is not None:
            write_account(xml_root, category.name, category.gnu_id, 'EXPENSE', None, DEFAULT_CURRENCY,
                          category.parent.gnu_id)


def write_fx_rates(xml_root):
    fx_rates = []

    # lookup fx rates from a file?
    if os.path.exists(fxscraper.OUTPUT_FILENAME):
        # hardcoded
        fx_rates.append(GnuFxRate('EUR', get_fx_rate('EUR', OPENING_BALANCE_DAY), OPENING_BALANCE_DAY))

        fx_tree = ET.parse(fxscraper.OUTPUT_FILENAME)
        for fx_element in fx_tree.findall('.//rate'):
            currency = fx_element.get('currency')
            fx_rate = fx_element.get('fx')
            day = datetime.strptime(fx_element.get('day'), '%Y-%m-%d').date()

            fx_rates.append(GnuFxRate(currency, fx_rate, day))
            fx_rates_map[(currency, day)] = float(fx_rate)

    else:
        # default fx routine
        for currency in sorted(CURRENCY_UNITS.keys()):
            if currency != DEFAULT_CURRENCY:
                fx_rates.append(GnuFxRate(currency, get_fx_rate(currency, OPENING_BALANCE_DAY), OPENING_BALANCE_DAY))

    pricedb = ET.SubElement(xml_root, 'gnc:pricedb', {'version': "1"})
    for fx_rate in fx_rates:
        price = ET.SubElement(pricedb, 'price')
        price_id = ET.SubElement(price, 'price:id', {'type': "guid"})
        price_id.text = next_id()
        add_currency_child(price, fx_rate.currency, 'price:commodity')
        add_currency_child(price, DEFAULT_CURRENCY, 'price:currency')
        add_timestamp(price, fx_rate.day, 'price:time')
        price_src = ET.SubElement(price, 'price:source')
        price_src.text = 'user:price-editor'
        price_type = ET.SubElement(price, 'price:type')
        price_type.text = 'unknown'
        price_value = ET.SubElement(price, 'price:value')
        price_value.text = str(Fraction(fx_rate.rate).limit_denominator())
