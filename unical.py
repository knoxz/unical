#!/usr/bin/python
# -*- coding: utf-8 -*-

#
# Extract calendar information from HIS-QIS room schedules.
#
# Usage:
#
# Author: rja
#
# Changes:
# 2015-02-13 (rja)
# - fix table parsing
# - cleanup code
# - add tests
# - add command line input
# 2015-01-28 (rja)
# - initial version

from __future__ import print_function
import re
import argparse
import requests
from pyquery import PyQuery as pq
from datetime import date, datetime, time, timedelta
from icalendar import Calendar, Event, vText

version = "0.1.0"


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

def get_url(url):
    response = requests.get(url)
    if (response.status_code == 200):
        return response.text
    else:
        raise HttpError(response.status_code, response.text)


def get_calendar(schedules, cal, cal_name):
    # calendar metadata
    if cal is None:
        cal = Calendar()
        cal.add('prodid', vText(schedules[0].room_name)+cal_name)
        cal.add('version', '2.0')
        cal.add('method','PUBLISH')
        
    for schedule in schedules:
        for reservation in schedule.reservations:
            event = Event()
            event.add('summary', reservation["title"])
            event.add('dtstart', reservation["start"])
            event.add('dtend', reservation["end"])
            event.add('url', reservation["href"])
            event['location'] = vText(schedule.room_name)
            cal.add_component(event)

    return cal

def write_calendar(calendar, filename):
    with open(filename, 'wb') as f:
        f.write(calendar.to_ical())

def isBlank (myString):
    if myString and myString.strip():
        #myString is not None AND myString is not empty or blank
        return False
    #myString is None OR myString is empty or blank
    return True


#
# represents a schedule for one room and one week
#
class Schedule:
    
    global max_cols, re_vor, re_nach

    max_cols = 9
    re_vor = re.compile("vor\s+([0-9]{1,2})")
    re_nach = re.compile("ab\s+([0-9]{1,2})")

    def __init__(self, html):
        # local variables
        self.room_name = ""
        self.reservations = []

        self.parse_room(html)

    def __str__(self):
        return "\n".join([str(r["start"]) + " - " + str(r["end"]) + ": " + r["title"] for r in self.reservations])

    def __repr__(self):
        return self.__str__()

    #
    # parse the HTML schedule
    #
    def parse_room(self, html):

        d = pq(html)

        self.room_name = d("html body div#wrapper div.divcontent div.content_max form.form table tr td h4 a.nav").text()
        self.week = int(d("html body div#wrapper div.divcontent div.content_max table.normal tr td.menu1_on fieldset form.form b").text().split(" ")[1])
        calname = vText(self.room_name)
        # the current time while parsing the table
        curr_time = {"hour" :  0, "minute" : 0}
        # found dates
        dates = []

        # Very tricky: due to row spans, it is difficult to find out the
        # actual column of a cell. We here store shifts that are caused by
        # rowspans.
        col_shift = []

        # HTML tables are stored row-by-row, thus we iteratue over all rows
        rows = d("html > body > div#wrapper > div.divcontent > div.content_max > form.form > table > tr")
        for r,row in enumerate(rows):

            # initialize column shift
            col_shift.append([0 for i in range(max_cols)])

            # extract the dates from the header
            cols = pq(row).find("th")
            for c,col in enumerate(cols):
                cold = pq(col)
                day = cold("div.klein").text()
                #print('xx'+day+'xx')
                if isBlank(day):
                    raise Exception('Only the current semester is supported.')
                dates.append(datetime.strptime(day, "%d.%m.%Y").date())

            # the non-header cells contain the reservations
            cols = pq(row).children("td")

            # get times and reservations
            for c,col in enumerate(cols):
                cold = pq(col)

                # shift to actual column
                act_col = c + col_shift[0][c]

                # get rowspan for this cell
                rowspan = 0
                rowspan_attr = cold.attr("rowspan")
                if rowspan_attr:
                    rowspan = int(rowspan_attr)

                # update shift information based on current rowspan
                self._handle_rowspan(col_shift, rowspan, act_col)

                if c == 0:
                    # extract time hour from the first column
                    tdplan = cold("span.normal").text()
                    curr_time = self._get_time(tdplan, curr_time)

                else:
                    # handle reservations
                    if cold.attr("class") == "plan2":
                        a = pq(cold("table tr td a.ver"))
                        if a:
                            # build start and end dates
                            today = dates[act_col - 2] # ignore first two columns
                            length = timedelta(minutes = 15 * rowspan)
                            start = datetime.combine(today, time(hour = curr_time["hour"], minute=curr_time["minute"]))
                            self.add_reservation(
                                start = start,
                                end = start + length,
                                title = a.attr("title"),
                                href = a.attr("href")
                            )

            # remove shift information for this row
            col_shift.pop(0)


    #
    # extract the time from the first column
    #
    def _get_time(self, tdplan, curr_time):
        if tdplan:
            match = re_vor.match(tdplan)
            if match:
                hour = int(match.group(1)) - 1
            else:
                match = re_nach.match(tdplan)
                if match:
                    hour = int(match.group(1))
                else:
                    hour = int(tdplan)
            # reset minute
            return {"hour" : hour, "minute" : 0}

        else:
            # increase minute
            return {"hour" : curr_time["hour"], "minute" : curr_time["minute"] + 15}

    def add_reservation(self, start, end, title, href):
        self.reservations.append({
            "start" : start,
            "end" : end,
            "title" : title,
            "href" : href
        })

    def _handle_rowspan(self, col_shift, rowspan, act_col):

        # increase cell shift for the next cells
        for rn in range(1, rowspan):
            # add new rows, if necessary
            if rn >= len(col_shift):
                col_shift.append([0 for i in range(max_cols)])
            # how much do we have to start to the left from this cell?
            shift = col_shift[rn][act_col]
            for cn in range(act_col - shift, max_cols):
                # consider rowspans to the right
                next_shift = 0
                if cn < max_cols - 1:
                    next_shift = col_shift[rn][cn + 1]
                # add shift information
                col_shift[rn][cn] = max(col_shift[rn][cn], next_shift) + 1



def get_file(name):
    with open(name, "r") as myfile:
        data = myfile.read()
    return data


if __name__ == '__main__':

    # configure command line parsing
    parser = argparse.ArgumentParser(description='Extract calendar information from HIS-QIS room schedules.', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-rid','--roomid', type=str, dest="roomids", help='enter roomid')
    parser.add_argument('-w', '--weeks', type=str, dest="weeks", help='enter start and end week. seperate with ,')
    parser.add_argument('-nw', '--nextweeks', type=str, dest="nextweeks", help='enter the relative number of weeks you want to be updated in advance')
    parser.add_argument('-d', '--debug', action="store_true", help='print debug information')
    parser.add_argument('-o', '--output', type=str, dest="out_file", default="save/schedule.ics", metavar="FILE", help='write output to FILE')
	#parser.add_argument('-rn', '--roomname', type=str, dest="cal_name", default="Uni Hannover GIS Calendar", help='calendar name')
    #/var/unical/unical/save/schedule.ics
    parser.add_argument('-v', '--version', action="version", version="%(prog)s " + version)
    parser.add_argument('-A', '--allroomids', action="store_true", help='parse all roomnumbers instead. THIS COULD TAKE SOME TIME!!!')
    

    args = parser.parse_args()
    
    #print(args.URL)
    #base_url = "http://qis.verwaltung.uni-hannover.de"
    #url = base_url + "/qisserver/rds?state=wplan&act=Raum&pool=Raum&show=plan&P.subc=plan&raum.rgid=1201"
    #url = base_url + "/qisserver/rds?state=wplan&act=Raum&pool=Raum&show=plan&P.subc=plan&raum.rgid=5710"
    #html = get_file("raum5710.html")
    #html = get_file("raum1201.html")
    #html = get_file("raum411_19.html")
    #http://qis.verwaltung.uni-hannover.de/qisserver/rds?state=wplan&act=Raum&pool=Raum&show=plan&P.subc=plan&raum.rgid=9402
    
    #http://qis.verwaltung.uni-hannover.de/qisserver/rds?state=wplan&act=Raum&pool=Raum&show=plan&P.subc=plan&raum.rgid=9402&week=27_2015
    
    
    baseUrl = 'http://qis.verwaltung.uni-hannover.de/qisserver/rds?state=wplan&act=Raum&pool=Raum&show=plan&P.subc=plan'
    roomArray = args.roomids.split(',')
    currentYear = date.today().year
    #currentYear = 2014
    #print(currentYear)
    
    if args.weeks is not None:
        weekArray = args.weeks.split(',')
        start = int(weekArray[0])
        end = int(weekArray[1])
    if args.nextweeks is not None:
        nextWeeks = int(args.nextweeks)
    
    
    if not args.allroomids and len(roomArray)>= 1 and args.nextweeks is None:
        a = datetime.now()
        calname = 'weeks'+str(start)+'till'+str(end)
        for roomid in roomArray:
            #   for w in weekArray: #weeks given as parameter    
            cal = None
            if(start > end):
                end = start + end
            for w in range(start,end+1): #weeks given as parameter     
                if (w > 53):
                    w = w - 53
                    html = get_url(baseUrl + '&raum.rgid='+roomid+'&week='+str(w)+'_'+str(currentYear+1))
                else:
                    html = get_url(baseUrl + '&raum.rgid='+roomid+'&week='+str(w)+'_'+str(currentYear))                
                schedule = Schedule(html)
                
                if args.debug:
                    print(schedule.__str__().encode("utf-8"))
                cal = get_calendar([schedule], cal, calname)
        write_calendar(cal, args.out_file+'room'+roomid+'week'+str(start)+'-'+str(end)+'.ics')
        if args.debug:
            b = datetime.now()
            d = b - a
            print(d.total_seconds())
            f = open("result.txt", "w")
            f.write("Total Time taken: "+str(d.total_seconds()))
            f.close()
    if args.nextweeks is not None and len(roomArray)>= 1:
        now = date.today().isocalendar()[1]
        calname = 'nextweek'+str(nextWeeks)
        for roomid in roomArray:
            #    for w in weekArray: #weeks given as parameter    
            cal = None
            for w in range(now,now+nextWeeks):
                if(w>53):
                    w = w - 53
                    html = get_url(baseUrl + '&raum.rgid='+roomid+'&week='+str(w)+'_'+str(currentYear+1))
                else:
                    html = get_url(baseUrl + '&raum.rgid='+roomid+'&week='+str(w)+'_'+str(currentYear))
                schedule = Schedule(html)
                
                if args.debug:
                    print(schedule.__str__().encode("utf-8"))
                cal = get_calendar([schedule], cal, calname)
        write_calendar(cal, args.out_file+'room'+roomid+'nextweeks'+str(nextWeeks)+'.ics')
                
    #else: #parse All rooms for all weeks SS15
        #html = get_file("rooms.html")
        #regex = re.compile('rgid=([0-9]*)')
        #roomids = regex.findall(html)
        #print(len(roomids))
        #print(roomids)
        #a = datetime.now()
        
        #for roomid in roomids:
        #    for i in range(16,31):
        #        html = get_url(baseUrl + '&raum.rgid='+roomid+'&week='+str(i)+'_2015')
        #        schedule = Schedule(html)
        #        calendar = get_calendar([schedule])
        #        write_calendar(calendar, args.out_file+'room'+roomid+'week'+str(i)+'.ics')
        #        
        #        if args.debug:
        #            print('checking room: '+roomid+' week: '+str(i))
        #            b = datetime.now()
        #            d = b - a
        #            print('TIME TAKEN:')
        #            print(d.total_seconds())
        #            print('----------')
        #b = datetime.now()
        #d = b - a
        #print('TOTAL TIME TAKEN!!!')
        #print(d.total_seconds())
        #f = open("result.txt", "w")
        #f.write("Total Time taken: "+str(d.total_seconds()))
        #f.close()
        