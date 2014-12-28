import xml.etree.ElementTree as ET
import xmloutput
import gzip
import uuid

input_filename = "c:\Users\Mitko\Downloads\Accounts.xml"
output_filename = "result.gnucash"
currencies = {'155': 'BGN', '43': 'EUR', '63': 'JPY', '140': 'USD'}


class AceAccountGroup:
    def __init__(self, ace_id, name):
        self.ace_id = ace_id
        self.name = name
        self.gnu_id = uuid.uuid4().get_hex()


class AceAccount:
    def __init__(self, ace_id, group, name, currency, balance, number, comment):
        self.ace_id = ace_id
        self.group = group
        self.name = name
        self.currency = currency
        self.balance = balance
        self.number = number
        self.comment = comment
        self.gnu_id = uuid.uuid4().get_hex()


class AceCategory:
    def __init__(self, ace_id, parent, name):
        self.ace_id = ace_id
        self.parent = parent
        self.name = name
        self.currency = xmloutput.default_currency
        self.gnu_id = uuid.uuid4().get_hex()


tree = ET.parse(input_filename)

account_groups = {}
accounts = {}
categories = {}
categories_by_name = {}

for group in tree.findall('.//AccountGroup'):
    group_id = group.find('AccountGroupID').get('ID')
    account_groups[group_id] = AceAccountGroup(group_id, group.get('Name'))

for account in tree.findall('.//Account'):
    currency_code = currencies[account.find('CurrencyID').get('ID')]
    group = account_groups[account.find('AccountGroupID').get('ID')]
    account_id = account.find('AccountID').get('ID')
    print group.name, ' / ', account.get('Name'), currency_code
    accounts[account_id] = AceAccount(account_id,
                                      group,
                                      account.get('Name'),
                                      currency_code,
                                      account.get('InitialBalance'),
                                      account.get('Number'),
                                      account.get('Comment'))

xml_categories = tree.findall('.//Category')
for category in xml_categories:
    category_id = category.find('CategoryID').get('ID')
    category_name = category.get('Name')
    if ':' not in category_name:
        ace_category = AceCategory(category_id, None, category_name)
        categories[category_id] = ace_category
        categories_by_name[category_name] = ace_category

for category in xml_categories:
    category_id = category.find('CategoryID').get('ID')
    category_name = category.get('Name')

    split = category_name.split(':')
    if len(split) == 2:
        parent = categories_by_name[split[0]]
        category_name = split[1]

        ace_category = AceCategory(category_id, parent, category_name)
        categories[category_id] = ace_category


# incomplete and BGN-specific
def get_fx_rate(currency, day):
    if currency == xmloutput.default_currency:
        return 1.0
    if currency == 'EUR':
        return 1.956
    if currency == 'USD':
        return 1.5
    if currency == 'JPY':
        return 0.015

def export_transaction(f, tran):
    tran_id = tran.find('TransactionID').get('ID')
    tran_day = tran.get('Date')

    # TODO: Support payeeID. Support splits
    if tran.find('CategoryID') is None:
        print 'Skip: TransactionID=', tran_id, ' is a split'
        return

    tran_accounts = tran.findall('AccountID')
    if len(tran_accounts) == 2:
        account_src = accounts[tran_accounts[1].get('ID')]
        account_dest = accounts[tran_accounts[0].get('ID')]
        amount_src = tran.get('TransferAmount')
        amount_dest = tran.get('Amount')
    else:
        account_src = accounts[tran_accounts[0].get('ID')]
        account_dest = categories[tran.find('CategoryID').get('ID')]
        amount_src = tran.get('Amount')
        amount_dest = str(float(amount_src) * get_fx_rate(account_src.currency, tran_day))

    f.write(xmloutput.write_transaction(account_src.currency,
                                        tran_day,
                                        tran.get('Comment'),
                                        xmloutput.GnuSplit(account_src.gnu_id, amount_src, account_src.currency),
                                        xmloutput.GnuSplit(account_dest.gnu_id, amount_dest, account_dest.currency)))


f = open(output_filename, 'w')
f.write(xmloutput.write_header())
f.write(xmloutput.write_commodities())
f.write(xmloutput.write_root_account())
f.write(xmloutput.write_opening_balances())
f.write(xmloutput.write_trading_accounts())
f.write(xmloutput.write_ace_categories(categories.values()))
f.write(xmloutput.write_ace_accounts(account_groups.values(), accounts.values()))
for tran in tree.findall('.//Transaction'):
    export_transaction(f, tran)
f.write(xmloutput.write_footer())
f.close()

f_in = open(output_filename, 'rb')
f_out = gzip.open(output_filename + '.gz', 'wb')
f_out.writelines(f_in)
f_out.close()
f_in.close()
