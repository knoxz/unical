#!/usr/bin/python
# -*- coding: utf-8 -*-

#
#
#
# Usage:
# 
# Author: rja 
#
# Changes:
# 2015-01-28 (rja)
# - initial version 

from __future__ import print_function
import re
import requests
from pyquery import PyQuery as pq
from datetime import date, datetime, time, timedelta
from icalendar import Calendar, Event, vText

re_vor = re.compile("vor\s+([0-9]{1,2})")
re_nach = re.compile("ab\s+([0-9]{1,2})")

class Error(Exception):
    """Base class for exceptions in this module."""
    pass


class HttpError(Error):
    def __init__(self, status, content):
        self.status = status
        self.content = content
    def __str__(self):
        if self.content != None:
            return repr(self.status) + " (" + str(self.content) + ")"
        return repr(self.status)

def get_room(url):
    response = requests.get(url)
    if (response.status_code == 200):
        return response.text
    else:
        raise HttpError(response.status_code, response.text)

def parse_room(html):
    max_cols = 9

    cal = Calendar()
    cal.add('prodid', '-//raumbelegung.py//l3s.de//')
    cal.add('version', '0.1')
    
    d = pq(html)
    room_name = d("html body div#wrapper div.divcontent div.content_max form.form table tr td h4 a.nav").text()
    print(room_name)

    curr_time_hour = 0
    curr_time_min = 0
    dates = []

    # Very tricky: due to row spans, it is difficult to find out the
    # actual column of a cell. We here store shifts that are caused by
    # rowspans.
    col_shift = []
    
    rows = d("html > body > div#wrapper > div.divcontent > div.content_max > form.form > table > tr")
    for r,row in enumerate(rows):            

        # get header
        cols = pq(row).find("th")
        for c,col in enumerate(cols):
            cold = pq(col)
            day = cold("div.klein").text()
            dates.append(datetime.strptime(day, "%d.%m.%Y").date())

        cols = pq(row).children("td")
        #print(str(r) + ": " + str(len(cols)))


        col_shift.append([0 for i in range(max_cols)])
        # get times and reservations
        for c,col in enumerate(cols):
            cold = pq(col)

            
            #print(str(r) + "," + str(c) + ": " + cold.text())

            
            # get actual column
            act_col = c
            if len(col_shift) > 0:
                # there exists shift information for this row
                act_col = c + col_shift[0][c]
                #print(str(c) + "->" + str(act_col))
            
            # get rowspan for this cell
            rowspan = 0
            rowspan_attr = cold.attr("rowspan")
            if rowspan_attr:
                rowspan = int(rowspan_attr)

            # add cell shift for the next cells (i.e., add +1 to all cols > act_col
            for cn in range(act_col - 1, max_cols):
                for rn in range(1,rowspan):
                    if rn >= len(col_shift):
                        col_shift.append([0 for i in range(max_cols)])
                    #print("len=" + str(len(col_shift)) + " / rn=" + str(rn) + ",cn=" + str(cn))
                    #print(col_shift[rn])
                    col_shift[rn][cn] = col_shift[rn][cn] + 1


            
            if c == 0:
                # extract time in first column
                tdplan = cold("span.normal").text()
                if tdplan:
                    match = re_vor.match(tdplan)
                    if match:
                        curr_time_hour = int(match.group(1)) - 1
                    else:
                        match = re_nach.match(tdplan)
                        if match:
                            curr_time_hour = int(match.group(1))
                        else:
                            curr_time_hour = int(tdplan)
                    curr_time_min = 0
                    #print("\n" + tdplan + ": " + str(curr_time_hour) + ":" + str(curr_time_min), end='')

                else:
                    curr_time_min = curr_time_min + 15
                    #print(", " + str(curr_time_hour) + ":" + str(curr_time_min), end='')
            else:
                # look for appointments
                if cold.attr("class") == "plan2":
                    # build start and end dates
                    today = dates[act_col - 2]
                    length = timedelta(minutes = 15 * rowspan)
                    start = datetime.combine(today, time(hour = curr_time_hour, minute=curr_time_min))
                    end = start + length
                    a = pq(cold("table tr td.klein a.ver"))
                    if a:
                        title = a.attr("title")
                        href = a.attr("href")
                        print(str(start) + "-" + str(end.time()) + ": " + title) #, end='')
                        if "Kapitalgesellschaftsrecht" in title or "Rechtshistorische" in title:
                            print(str(r) + "," + str(c) + "->" + str(act_col))
                            array_print(col_shift)
                        event = Event()
                        event.add('summary', title)
                        event.add('dtstart', start)
                        event.add('dtend', end)
                        event['location'] = vText(room_name)
                        cal.add_component(event)

                        
        # remove box for this row
        if len(col_shift) > 0:
            col_shift.pop(0)


    return cal
#
# Addition of two arrays. If one array is longer, the shorter is
# padded with zeros.
#
def array_addition(a, b):
    result = [x + y for x,y in zip(a, b)]
    if len(a) > len(b):
        result.extend(a[len(b):])
    else:
        result.extend(b[len(a):])
    return result

# print a two-dimensional array, organized by [ row, row, row ]
def array_print(a):
    for i in range(len(a)):
        b = a[i]
        print("".join([str(x) for x in b]))
        


def get_file(name):
    with open(name, "r") as myfile:
        data = myfile.read()
    return data
    
if __name__ == '__main__':
    base_url = "http://qis.verwaltung.uni-hannover.de"
    url = base_url + "/qisserver/rds?state=wplan&act=Raum&pool=Raum&show=plan&P.subc=plan&raum.rgid=1201"
    url = base_url + "/qisserver/rds?state=wplan&act=Raum&pool=Raum&show=plan&P.subc=plan&raum.rgid=5710"
    html = get_room(url)
    #html = get_file("raum1201.html")
    cal = parse_room(html)

    with open('example.ics', 'wb') as f:
        f.write(cal.to_ical())
