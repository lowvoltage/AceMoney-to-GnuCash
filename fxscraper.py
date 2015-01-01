import xml.etree.ElementTree as ET
import urllib
import time
from datetime import datetime
import xmloutput

start_year = 2004
end_year = 2014
output_filename = 'fxrates.xml'

base_url = "http://www.bnb.bg/Statistics/StExternalSector/StExchangeRates/StERForeignCurrencies/index.htm" \
      "?downloadOper=&group1=second&" \
      "periodStartDays=01&periodStartMonths={0}&periodStartYear={1}&" \
      "periodEndDays=10&periodEndMonths={0}&periodEndYear={1}&" \
      "valutes={2}&search=true"

xml_root = ET.Element('rates')

# iterate all currencies, all years, all months
for currency in ('USD', 'JPY'):
    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            # setup request url, get
            url = base_url.format(month, year, currency)
            page_lines = urllib.urlopen(url).read().splitlines()

            # locate the FX-rates table start & end
            open_line_index = page_lines.index('<tbody>')
            close_line_index = page_lines.index('</tbody>')

            # extract
            sub_list = page_lines[open_line_index:close_line_index + 1]
            sub_string = '\n'.join(sub_list)

            # parse it as an xml
            tree = ET.fromstring(sub_string)

            # retrieve values of interest
            day = ''
            value = ''
            multi = ''
            first_row = tree.find('.//tr')
            for cell in first_row.findall('.//td'):
                if cell.get('class') == 'first':
                    day = cell.text
                if cell.get('class') == 'right':
                    multi = cell.text
                if cell.get('class') == 'last right':
                    value = cell.text

            parsed_day = datetime.strptime(day, '%d.%m.%Y').date()
            parsed_fx = str(float(value) / float(multi))
            start_of_month_day = parsed_day.replace(day=1)

            # export to our xml
            print currency, parsed_day, parsed_fx
            ET.SubElement(xml_root, 'rate', {'day': str(start_of_month_day), 'currency': currency, 'fx': parsed_fx})

            # cool-off timeout
            time.sleep(0.1)

print
print 'Open for writing', output_filename
xmloutput.indent(xml_root)
ET.ElementTree(xml_root).write(output_filename, 'utf-8', True)
