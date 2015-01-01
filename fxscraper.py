import xml.etree.ElementTree as ET
import urllib
import time
from datetime import date, datetime
from config import indent


LOOKUP_CURRENCIES = ('USD', 'JPY')
START_YEAR = 2004
OUTPUT_FILENAME = 'fxrates.xml'
BASE_URL = "http://www.bnb.bg/Statistics/StExternalSector/StExchangeRates/StERForeignCurrencies/index.htm" \
           "?downloadOper=&group1=second&" \
           "periodStartDays=01&periodStartMonths={0}&periodStartYear={1}&" \
           "periodEndDays=10&periodEndMonths={0}&periodEndYear={1}&" \
           "valutes={2}&search=true"


def get_bgn_fx_rate(currency, start_of_month):
    # setup request url, get response
    url = BASE_URL.format(start_of_month.month, start_of_month.year, currency)
    page_lines = urllib.urlopen(url).read().splitlines()

    try:
        # locate the FX-rates table start & end. can throw an exception
        open_line_index = page_lines.index('<tbody>')
        close_line_index = page_lines.index('</tbody>')

        # extract
        sub_list = page_lines[open_line_index:close_line_index + 1]
        sub_string = '\n'.join(sub_list)

        # parse it as an xml
        tree = ET.fromstring(sub_string)

        # retrieve values of interest from the first table row (SOM or nearest day)
        value = ''
        multi = ''
        first_row = tree.find('.//tr')
        for cell in first_row.findall('.//td'):
            if cell.get('class') == 'right':
                multi = cell.text
            if cell.get('class') == 'last right':
                value = cell.text

        return str(float(value) / float(multi))
    except ValueError:
        # no FXs for the requested month
        return None


def main():
    print 'Retrieving BGN FX-rates for', LOOKUP_CURRENCIES, 'since', START_YEAR
    xml_root = ET.Element('rates')

    # lookup days are common for all currencies
    lookup_days = []
    for year in range(START_YEAR, datetime.today().year + 1):
        for month in range(1, 13):
            lookup_days.append(date(year, month, 1))

    # iterate all currencies, all days
    for currency in LOOKUP_CURRENCIES:
        for start_of_month in lookup_days:
            fx_rate = get_bgn_fx_rate(currency, start_of_month)
            if fx_rate is None:
                print 'Stop: No values found for', currency, 'on', start_of_month
                break

            # export to our xml
            print currency, start_of_month, fx_rate
            ET.SubElement(xml_root, 'rate', {'day': str(start_of_month), 'currency': currency, 'fx': fx_rate})

            # cool-off timeout
            time.sleep(0.1)

    print
    print 'Open for writing', OUTPUT_FILENAME
    indent(xml_root)
    ET.ElementTree(xml_root).write(OUTPUT_FILENAME, 'utf-8', True)
    print 'Done'


if __name__ == "__main__":
    main()
