# studip_nextcloud_calendar

## analyse_csv.py

What it does: It downloads the current room occupancy of a given room from StudIP Raumverwaltung and syncs it with a NextCloud Calendar with the same name. 

What you need to do: Change all the parts marked with TODO as well as create the corresponding NextCloud calendar.

  Very important!!! Make sure that the calendar for the room exists under NextCloud calendar. The name for the calendar needs to be the same as in the column Raumname in the CSV file from Raumverwaltung StudIP. 

  Make sure that you fill in the correct user data (i.e. zfn user and passwort for StudIP as well as a NextCloud application user and passwort). 

  Also change the working directory. There a file with the name DONE is touched. e.g. for Nagios supervision.

  You need to edit the list of room ids (which you steal.. get... from the Raumverwaltung section of StudIP). 

I tested and use a slightly different version under Linux sucessfully (Python 3.11.2). My version was speciallized for the Cognium building. I removed this specialization but hadn't the time to test the modified version yet. I run this tool in a cron job. I intentionally slowed to the tool to prevent to much workload for the StudIP system. Change the sleep time values if you don't like this. 




