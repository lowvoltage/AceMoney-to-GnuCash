import xml.etree.ElementTree as ET
import config
import gnucashxmlwriter
import gzip
import argparse
import sys
from datetime import datetime

# TODO: General code style; Docs
ace_currency_codes = {'155': 'BGN', '43': 'EUR', '63': 'JPY', '140': 'USD'}
processed_count = 0


class AceAccountGroup:
    def __init__(self, ace_id, name):
        self.ace_id = ace_id
        self.name = name
        self.gnu_id = config.next_id()


class AceAccount:
    def __init__(self, ace_id, group, name, currency, balance, number, comment, hidden):
        self.ace_id = ace_id
        self.group = group
        self.name = name
        self.currency = currency
        self.balance = balance
        self.number = number
        self.comment = comment
        self.hidden = hidden
        self.gnu_id = config.next_id()


class AceCategory:
    def __init__(self, ace_id, parent, name):
        self.ace_id = ace_id
        self.parent = parent
        self.name = name
        self.currency = config.DEFAULT_CURRENCY
        self.gnu_id = config.next_id()


account_groups = {}
accounts = {}
categories = {}
categories_by_name = {}
payees = {}

arg_parser = argparse.ArgumentParser(description="AceMoney to GnuCash converter")
arg_parser.add_argument("-i", dest="input_filename", required=True, help="input .xml filename, exported from AceMoney",
                        metavar="FILE")
arg_parser.add_argument("-o", dest="output_filename", required=True, help="output .gnucash filename", metavar="FILE")
args = arg_parser.parse_args()

tree = ET.parse(args.input_filename)
print 'Loaded', args.input_filename
print

payee_elements = tree.findall('.//Payee')
print 'Found', len(payee_elements), 'payees:'
for payee in payee_elements:
    payee_id = payee.find('PayeeID').get('ID')
    payee_name = payee.get('Name')
    payees[payee_id] = payee_name
    print(u"Payee ID={0} '{1}'".format(payee_id, payee_name))
print

account_group_elements = tree.findall('.//AccountGroup')
print 'Found', len(account_group_elements), 'account groups:'
for group in account_group_elements:
    group_id = group.find('AccountGroupID').get('ID')
    group_name = group.get('Name')
    account_groups[group_id] = AceAccountGroup(group_id, group_name)
    print(u"Group ID={0} '{1}'".format(group_id, group_name))
print

account_elements = tree.findall('.//Account')
print 'Found', len(account_elements), 'accounts:'
for account in account_elements:
    currency_code = ace_currency_codes[account.find('CurrencyID').get('ID')]
    group = account_groups[account.find('AccountGroupID').get('ID')]
    account_id = account.find('AccountID').get('ID')
    account_name = account.get('Name')
    account_balance = account.get('InitialBalance')

    print(u"Account ID={0} '{1} / {2}'".format(account_id, group.name, account_name))

    accounts[account_id] = AceAccount(account_id, group, account_name, currency_code,
                                      account_balance, account.get('Number'), account.get('Comment'),
                                      account.get('IsClosed') == 'TRUE')
print

category_elements = tree.findall('.//Category')
print 'Found', len(category_elements), 'categories:'
for category in category_elements:
    category_id = category.find('CategoryID').get('ID')
    category_name = category.get('Name')
    if ':' not in category_name:
        print(u"TopCategory ID={0} '{1}'".format(category_id, category_name))
        ace_category = AceCategory(category_id, None, category_name)
        categories[category_id] = ace_category
        categories_by_name[category_name] = ace_category

for category in category_elements:
    category_id = category.find('CategoryID').get('ID')
    category_name = category.get('Name')

    split = category_name.split(':')
    if len(split) == 2:
        print(u"Category ID={0} '{1}'".format(category_id, category_name))
        parent = categories_by_name[split[0]]
        category_name = split[1]

        ace_category = AceCategory(category_id, parent, category_name)
        categories[category_id] = ace_category

default_category = AceCategory(-1, None, 'Unassigned')
categories[-1] = default_category
print


def get_payee_name(tran):
    payee_elem = tran.find('PayeeID')
    tran_payee = None
    if payee_elem is not None:
        tran_payee = payees[payee_elem.get('ID')]
    return tran_payee


def export_transaction(writer, tran):
    global processed_count
    if processed_count % 100 == 0:
        sys.stdout.write('.')
    processed_count += 1

    tran_day = tran.get('Date')
    tran_id = tran.find('TransactionID').get('ID')

    if tran.find('CategoryID') is None:
        tran_cat_id = -1
    else:
        tran_cat_id = tran.find('CategoryID').get('ID')

    tran_accounts = tran.findall('AccountID')
    if len(tran_accounts) == 2:
        account_src = accounts[tran_accounts[1].get('ID')]
        account_dst = accounts[tran_accounts[0].get('ID')]
        amount_src = tran.get('TransferAmount')
        amount_dst = tran.get('Amount')
    else:
        account_src = accounts[tran_accounts[0].get('ID')]
        account_dst = categories[tran_cat_id]
        amount_src = tran.get('Amount')
        day = datetime.strptime(tran_day, '%Y-%m-%d').date()
        amount_dst = str(float(amount_src) * config.get_fx_rate(account_src.currency, day))

    # Note: Limitations - 'cleared' state is ignored; The flag for the second transaction leg (if present) is ignored
    reconciled = tran.find('TransactionState').get('State') == '1'

    description = config.concat(get_payee_name(tran), tran.get('Comment'), ': ')

    writer.write_transaction(account_src.currency, tran_day, description, tran_id, reconciled,
                             gnucashxmlwriter.Split(account_src.gnu_id, amount_src, account_src.currency),
                             gnucashxmlwriter.Split(account_dst.gnu_id, amount_dst, account_dst.currency))


def get_sorted_transactions():
    sorted_pairs = []
    for tran in tree.findall('.//Transaction'):
        sorted_pairs.append((tran.get('Date'), tran))
    sorted_pairs.sort()
    return [item[-1] for item in sorted_pairs]


def create_zip(output_filename, output_gz_filename):
    f_in = open(output_filename, 'rb')
    f_out = gzip.open(output_gz_filename, 'wb')
    print 'Open for writing', output_gz_filename
    f_out.writelines(f_in)
    f_out.close()
    f_in.close()


transactions = get_sorted_transactions()
print 'Found', len(transactions), 'transactions'

writer = gnucashxmlwriter.GnuCashXmlWriter()
writer.load_skeleton('skeleton.gnucash')
writer.write_commodities()
writer.write_fx_rates()
writer.write_root_account()
writer.write_opening_balances()
writer.write_trading_accounts()
writer.write_ace_categories(categories.values())
writer.write_ace_account_groups(account_groups.values())
writer.write_ace_accounts(accounts.values())
for tran in transactions:
    export_transaction(writer, tran)
writer.save(args.output_filename)

create_zip(args.output_filename, args.output_filename + '.gz')

print 'Done'
