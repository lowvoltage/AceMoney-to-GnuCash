import xml.etree.ElementTree as ET
import uuid
from fractions import Fraction

# define default currency and all involved currencies, with their sub-units
default_currency = 'BGN'
currencies = {'BGN': '100', 'USD': '100', 'EUR': '100', 'JPY': '1'}
opening_balance_day = '2000-01-01'

# auto-generated IDs
def next_id():
    return uuid.uuid4().get_hex()


root_account_id = next_id()
equity_account_id = next_id()
opening_balances_account_id = next_id()
opening_balances_accounts_ids = {}

trading_account_id = next_id()
trading_currency_account_id = next_id()
trading_currency_account_ids = {}

expenses_account_id = next_id()

placeholder = {'placeholder': 'true'}

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


# incomplete and BGN-specific
def get_fx_rate(currency, day):
    if currency == default_currency:
        return 1.0
    if currency == 'EUR':
        return 1.95583
    if currency == 'USD':
        return 1.5
    if currency == 'JPY':
        return 0.015


def write_header():
    with open("header.xml", "r") as header:
        return header.read()


def write_footer():
    with open("footer.xml", "r") as footer:
        return footer.read()


def write_currency_commodity(element, currency):
    cmd_space = ET.SubElement(element, 'cmdty:space')
    cmd_space.text = 'ISO4217'
    cmd_space = ET.SubElement(element, 'cmdty:id')
    cmd_space.text = currency


def write_commodities():
    result = ''
    for currency in sorted(currencies.keys()):
        commodity = ET.Element('gnc:commodity', {'version': "2.0.0"})
        write_currency_commodity(commodity, currency)
        ET.SubElement(commodity, 'cmdty:get_quotes')
        cmd_src = ET.SubElement(commodity, 'cmdty:quote_source')
        cmd_src.text = 'currency'
        ET.SubElement(commodity, 'cmdty:quote_tz')

        result += toxmlstring(commodity)

    with open("commodities.xml", "r") as comm:
        result += comm.read()
    return result


def write_root_account():
    return write_account('Root Account', root_account_id, 'ROOT', None, default_currency, None)


def write_opening_balances():
    # create Equity and Equity:Opening Balances accounts
    result = write_account('Equity', equity_account_id, 'EQUITY', None, default_currency, root_account_id,
                           placeholder)
    result += write_account('Opening Balances', opening_balances_account_id, 'EQUITY', None, default_currency,
                            equity_account_id, placeholder)

    # create sub-accounts for each specified currency
    for currency in sorted(currencies.keys()):
        # generate and map the ID
        account_id = next_id()
        opening_balances_accounts_ids[currency] = account_id

        result += write_account(currency, account_id, 'EQUITY', None, currency, opening_balances_account_id)

    return result


def write_trading_accounts():
    # create Trading and Trading:CURRENCY accounts
    result = write_account('Trading', trading_account_id, 'TRADING', None, default_currency, root_account_id,
                           placeholder)
    result += write_account('CURRENCY', trading_currency_account_id, 'TRADING', None, default_currency,
                            trading_account_id, placeholder)

    # create sub-accounts for each specified currency
    for currency in sorted(currencies.keys()):
        # generate and map the ID
        account_id = next_id()
        trading_currency_account_ids[currency] = account_id

        result += write_account(currency, account_id, 'TRADING', None, currency, trading_currency_account_id)

    return result


def add_currency_child(parent_element, currency, child_tag_name):
    act_commodity = ET.SubElement(parent_element, child_tag_name)
    write_currency_commodity(act_commodity, currency)


def add_timestamp(parent_element, day, child_tag_name):
    date_outer = ET.SubElement(parent_element, child_tag_name)
    date_inner = ET.SubElement(date_outer, 'ts:date')
    date_inner.text = day + ' 00:00:00 +0200'


def toxmlstring(element):
    indent(element)
    return ET.tostring(element, 'utf-8')


def write_account(name, account_id, account_type, account_code, currency, parent_id, slots=None):
    acc = ET.Element('gnc:account', {'version': "2.0.0"})
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
    act_scu.text = currencies[currency]
    # if description is not None:
    # act_desc = ET.SubElement(acc, 'act:description')
    #     act_desc.text = description
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

    return toxmlstring(acc)


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


def build_comment(account):
    comment = ''
    if account.comment is not None:
        comment = account.comment + '\n'
    return comment + 'AceID=' + account.ace_id + ' Balance=' + account.balance


def write_ace_accounts(account_groups, accounts):
    result = ''

    # create a top-level account for each AceMoney group
    for group in account_groups:
        slots = placeholder.copy()
        slots['notes'] = 'AceGroupID=' + group.ace_id
        result += write_account(group.name, group.gnu_id, 'BANK', None, default_currency, root_account_id, slots)

    # create an account for each AceMoney account
    for account in accounts:
        slots = {'notes': build_comment(account)}
        result += write_account(account.name, account.gnu_id, 'BANK', account.number, account.currency,
                                account.group.gnu_id, slots)

    # setup the initial balance transaction for each AceMoney account
    for account in accounts:
        result += write_opening_balance_transaction(account)

    return result


def write_opening_balance_transaction(account):
    if account.balance == '0':
        return ''

    return write_transaction(account.currency, opening_balance_day, None, None,
                             GnuSplit(account.gnu_id, account.balance, account.currency),
                             GnuSplit(opening_balances_accounts_ids[account.currency], account.balance,
                                      account.currency))


def add_split(splits, value, quantity, account):
    split = ET.SubElement(splits, 'trn:split')

    split_id = ET.SubElement(split, 'split:id', {'type': "guid"})
    split_id.text = next_id()
    split_rec = ET.SubElement(split, 'split:reconciled-state')
    split_rec.text = 'n'
    split_value = ET.SubElement(split, 'split:value')
    split_value.text = value
    split_quantity = ET.SubElement(split, 'split:quantity')
    split_quantity.text = quantity
    split_acc = ET.SubElement(split, 'split:account', {'type': "guid"})
    split_acc.text = account


def write_transaction(currency, day, description, num, split_src, split_dest):
    tran = ET.Element('gnc:transaction', {'version': "2.0.0"})
    tran_id = ET.SubElement(tran, 'trn:id', {'type': "guid"})
    tran_id.text = next_id()
    add_currency_child(tran, currency, 'trn:currency')
    add_timestamp(tran, day, 'trn:date-posted')
    add_timestamp(tran, day, 'trn:date-entered')

    tran_desc = ET.SubElement(tran, 'trn:description')
    if description is not None:
        tran_desc.text = description
    tran_num = ET.SubElement(tran, 'trn:num')
    if num is not None:
        tran_num.text = num
    tran_slots = ET.SubElement(tran, 'trn:slots')
    tran_slot = ET.SubElement(tran_slots, 'slot')
    tran_slot_key = ET.SubElement(tran_slot, 'slot:key')
    tran_slot_key.text = 'date-posted'
    tran_slot_value = ET.SubElement(tran_slot, 'slot:value', {'type': "gdate"})
    gdate = ET.SubElement(tran_slot_value, 'gdate')
    gdate.text = day

    multiplier_src = currencies[split_src.currency]
    amount_src = int(round(float(split_src.amount) * float(multiplier_src)))

    multiplier_dest = currencies[split_dest.currency]
    amount_dest = int(round(float(split_dest.amount) * float(multiplier_dest)))

    tran_splits = ET.SubElement(tran, 'trn:splits')

    if split_src.currency == split_dest.currency:
        value_src = str(amount_src) + '/' + multiplier_src
        value_dest = str(-amount_dest) + '/' + multiplier_dest
        add_split(tran_splits, value_src, value_src, split_src.account_id)
        add_split(tran_splits, value_dest, value_dest, split_dest.account_id)

    else:
        value_src_pos = str(amount_src) + '/' + multiplier_src
        value_src_neg = str(-amount_src) + '/' + multiplier_src
        value_dest_pos = str(amount_dest) + '/' + multiplier_dest
        value_dest_neg = str(-amount_dest) + '/' + multiplier_dest
        add_split(tran_splits, value_src_pos, value_src_pos, split_src.account_id)
        add_split(tran_splits, value_src_neg, value_dest_neg, split_dest.account_id)

        # generate trading account entries
        add_split(tran_splits, value_src_neg, value_src_neg, trading_currency_account_ids[split_src.currency])
        add_split(tran_splits, value_src_pos, value_dest_pos, trading_currency_account_ids[split_dest.currency])

    return toxmlstring(tran)


def write_ace_categories(categories):
    result = write_account('Expense', expenses_account_id, 'EXPENSE', None, default_currency, root_account_id,
                           placeholder)

    for category in categories:
        if category.parent is None:
            result += write_account(category.name, category.gnu_id, 'EXPENSE', None, default_currency,
                                    expenses_account_id)

    for category in categories:
        if category.parent is not None:
            result += write_account(category.name, category.gnu_id, 'EXPENSE', None, default_currency,
                                    category.parent.gnu_id)

    return result


def write_fx_rates():
    fx_rates = []
    for currency in sorted(currencies.keys()):
        if currency != default_currency:
            fx_rates.append(GnuFxRate(currency, get_fx_rate(currency, opening_balance_day), opening_balance_day))

    pricedb = ET.Element('gnc:pricedb', {'version': "1"})
    for fx_rate in fx_rates:
        price = ET.SubElement(pricedb, 'price')
        price_id = ET.SubElement(price, 'price:id', {'type': "guid"})
        price_id.text = next_id()
        add_currency_child(price, fx_rate.currency, 'price:commodity')
        add_currency_child(price, default_currency, 'price:currency')
        add_timestamp(price, fx_rate.day, 'price:time')
        price_src = ET.SubElement(price, 'price:source')
        price_src.text = 'user:price-editor'
        price_type = ET.SubElement(price, 'price:type')
        price_type.text = 'unknown'
        price_value = ET.SubElement(price, 'price:value')
        price_value.text = str(Fraction(fx_rate.rate).limit_denominator())

    return toxmlstring(pricedb)
