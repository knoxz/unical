# unical

Extracts calendar information for rooms from university web pages that
are based on HIS-QIS and generates an iCalendar file.

## dependencies

- [requests](https://pypi.python.org/pypi/requests)
- [pyquery](https://pypi.python.org/pypi/pyquery)
- [icalendar](https://pypi.python.org/pypi/icalendar)

Install requirements with:
pip install -r requirements.txt

## parameter

 - -rid xxx   ( xxx stands for the room id)
 - -w xx,xx   ( first is start week, 2nd is endweek for the requested timespan)
 - -nw xx     ( number of weeks the script gives you from the current one. For example -nw 2 will give you the dates for
              next 2 weeks. The script will update them automatically.)
 - -o outputfile (path and filename for the output file. The system will automatically add the end of the filename.)
 - -d         ( enable debugging like time taken for the requests or other stuff.)
 - -v         ( returns the version.)
