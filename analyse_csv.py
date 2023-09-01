import glob
import pandas as pd
import caldav
import datetime
from dateutil.relativedelta import relativedelta  # type: ignore
import pytz  # type: ignore
import create_logger

from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.common.by import By
import time
import os
from pathlib import Path


def login(
    driver: webdriver.firefox.webdriver.WebDriver,
    base_url: str,
    zfn_user: str,
    zfn_password: str,
    logger,
) -> bool:
    assert len(base_url) > 0
    assert len(zfn_user) > 0
    assert len(zfn_password) > 0

    login_url: str = base_url

    # Login
    driver.get(login_url)
    print_new_line: bool = False
    while driver.current_url != login_url:
        logger.info(".")
        time.sleep(1)
        print_new_line = True

    if print_new_line is True:
        logger.info("")

    login_name_list = driver.find_elements(By.ID, "loginname")
    login_password_list = driver.find_elements(By.ID, "password")
    login_button_list = driver.find_elements(By.NAME, "Login")

    if (
        (len(login_name_list) != 1)
        and (len(login_password_list) != 1)
        and (len(login_button_list) != 1)
    ):
        return False

    login_name = login_name_list[0]
    login_password = login_password_list[0]
    login_button = login_button_list[0]

    while (login_name.get_attribute("value") != zfn_user) or (
        login_password.get_attribute("value") != zfn_password
    ):
        login_name.clear()
        login_password.clear()
        login_name.send_keys(zfn_user)
        login_password.send_keys(zfn_password)
        time.sleep(1)

    login_button.click()
    while driver.current_url == login_url:
        print(".", end="")
        time.sleep(1)
        print_new_line = True

    if print_new_line is True:
        print()

    return str(driver.current_url).startswith(
        "https://elearning.uni-bremen.de/dispatch.php/start"
    )


def download(
    path: str,
    login_url: str,
    zfn_user: str,
    zfn_password: str,
    logger,
    link_room_id: str,
) -> None:
    os.makedirs(path, exist_ok=True)
    for file in glob.glob(os.path.join(path, "*.csv")):
        os.remove(file)

    options = webdriver.FirefoxOptions()
    options.set_preference("browser.download.folderList", 2)  # custom location
    options.set_preference("browser.download.manager.showWhenStarting", False)
    options.set_preference("browser.download.dir", path)
    options.set_preference("browser.helperApps.neverAsk.saveToDisk", "text/csv")
    options.add_argument("-headless")

    driver = webdriver.Firefox(
        options=options, service=FirefoxService(GeckoDriverManager().install())
    )

    result: bool = login(
        driver=driver,
        base_url=login_url,
        zfn_user=zfn_user,
        zfn_password=zfn_password,
        logger=logger,
    )

    assert result

    todo_url: str = (
        str(
            "https://elearning.uni-bremen.de/dispatch.php/resources/export/resource_bookings/"
        )
        + link_room_id
    )
    driver.get(todo_url)

    print_new_line: bool = False
    while driver.current_url != todo_url:
        print(".", end="")
        time.sleep(1)
        print_new_line = True

    if print_new_line is True:
        print()

    end_date_list = driver.find_elements(By.NAME, "end_date")
    export_button_list = driver.find_elements(By.NAME, "export")
    assert len(end_date_list) == 1
    assert len(export_button_list) == 1

    end_date = end_date_list[0]
    export_button = export_button_list[0]

    # Get the date and increase it by 2 years
    date_to_modify = end_date.get_attribute("value")

    date_to_modify_dt: datetime.datetime = datetime.datetime.strptime(
        str(date_to_modify), "%d.%m.%Y"
    )
    date_to_modify_dt = date_to_modify_dt + relativedelta(years=2)

    date_to_modify = date_to_modify_dt.strftime("%d.%m.%Y")

    end_date.clear()
    end_date.send_keys(date_to_modify)

    found_element_list = driver.find_elements(By.TAG_NAME, "button")
    close_button_class: str = (
        "ui-datepicker-close ui-state-default ui-priority-primary ui-corner-all"
    )
    for id in range(0, len(found_element_list)):
        if str(found_element_list[id].get_dom_attribute("class")).startswith(
            close_button_class
        ):
            found_element_list[id].click()
            time.sleep(1)
            break

    export_button.click()

    time.sleep(10)
    driver.close()
    driver.quit()


def process(
    path: str,
    time_start: datetime.datetime,
    time_end: datetime.datetime,
    nextcloud_url: str,
    nextcloud_app_user: str,
    nextcloud_app_password: str,
    studip_room_name: str,
    studip_start: str,
    studip_end: str,
    studip_description: str,
    studip_person: str,
    logger,
) -> None:
    files = glob.glob(os.path.join(path, "*.csv"))

    if len(files) == 0:
        exit(0)

    with caldav.DAVClient(
        url=nextcloud_url, username=nextcloud_app_user, password=nextcloud_app_password
    ) as client:
        my_principal = client.principal()
        calendars = my_principal.calendars()

        assert len(calendars) > 0

        for filename in files:
            df = pd.read_csv(filename, sep=";", header=0)
            csv_room_namelist = df[studip_room_name].unique()

            # The file should only contain one room
            assert len(csv_room_namelist) == 1
            csv_room_name: str = str(csv_room_namelist[0])

            logger.info(f"Processing room: {csv_room_name}")

            calender_caldav_object = None
            for id in range(0, len(calendars)):
                if str(calendars[id]).endswith(csv_room_name):
                    calender_caldav_object = calendars[id]
                    break

            assert calender_caldav_object is not None

            all_events = calender_caldav_object.search(
                start=time_start,
                end=time_end,
                event=True,
            )

            for event_selection in all_events:
                event_summary = str(
                    event_selection.vobject_instance.vevent.summary.value
                )
                event_dtstart = event_selection.icalendar_component.get(
                    "dtstart"
                ).dt.strftime("%d.%m.%Y %H:%M")
                event_dtend = event_selection.icalendar_component.get(
                    "dtend"
                ).dt.strftime("%d.%m.%Y %H:%M")

                temp_df = df[
                    (df[studip_start] == event_dtstart)
                    * (df[studip_end] == event_dtend)
                ]

                assert len(temp_df) >= 0
                assert len(temp_df) <= 1

                # This event needs to be deleted...
                # because it isn't in the studip list anymore
                if len(temp_df) == 0:
                    event_selection.delete()
                    logger.info("Event deleted from NextCloud")
                # Remove the existing correct dates from the panda data frame
                else:
                    temp_summary: str = f"{temp_df[studip_description].iloc[0]} ({temp_df[studip_person].iloc[0]})"
                    if event_summary != temp_summary:
                        logger.info("Need to update summary!!!")
                        event_selection.vobject_instance.vevent.summary.value = (
                            temp_summary
                        )
                        event_selection.save()

                    df.drop(inplace=True, index=int(temp_df.iloc[0].name))

            # Add the remaining list of events
            for id in range(0, len(df)):
                dtstart: datetime.datetime = datetime.datetime.strptime(
                    str(df[studip_start].iloc[id]), "%d.%m.%Y %H:%M"
                )
                dtstart = dtstart.replace(tzinfo=pytz.timezone("Europe/Berlin"))
                dtend: datetime.datetime = datetime.datetime.strptime(
                    str(df[studip_end].iloc[id]), "%d.%m.%Y %H:%M"
                )
                dtend = dtend.replace(tzinfo=pytz.timezone("Europe/Berlin"))

                summary: str = (
                    f"{df[studip_description].iloc[id]} ({df[studip_person].iloc[id]})"
                )

                _ = calender_caldav_object.save_event(
                    dtstart=dtstart, dtend=dtend, summary=summary, tzid="Europe/Berlin"
                )

                logger.info(f"Adding ({id} / {len(df)-1}): {dtstart} {dtend} {summary}")


# #############################################
# Parameter:
# #############################################

# Time slice: from today until + 2 years
time_start: datetime.datetime = datetime.datetime.now()
time_start = time_start.replace(hour=0, minute=0)
time_end: datetime.datetime = time_start + relativedelta(years=2)

# StudIP
login_url: str = "https://elearning.uni-bremen.de/index.php?again=yes"
# TODO: Change zfn username for studip
zfn_user: str = "XXXXX"
# TODO: Change zfn password for studip
zfn_password: str = "XXXXX"

# Nextcloud
nextcloud_url: str = "https://nc.uni-bremen.de/remote.php/dav"
# TODO: Change nextcloud application username
nextcloud_app_user: str = "XXXXX@uni-bremen.de"
# TODO: Change nextcloud application passwort
nextcloud_app_password: str = "XXXXX-XXXXX-XXXXX-XXXXX-XXXXX"

# Stud IP CSV parameters
studip_room_name: str = "Raumname"
studip_start: str = "Beginn"
studip_end: str = "Ende"
studip_description: str = "Beschreibung"
studip_person: str = "Belegende Person(en)"

# To prevent download dialog
path: str = "/tmp/studip"

# TODO: Change room list using the IDs from StudIP
link_room_id_list: list[str] = [
    "r0000000000000000000000000018077",  # Cog 0320
    "342f7053793665a151872ae455943e1a",  # Cog 1370
    "r0000000000000000000000000018047",  # Cog 1030
    "r0000000000000000000000000018048",  # Cog 2030
]

# TODO: Change working directory
working_dir: str = "/0/Service/nextcloud_cal"

logger = create_logger.create_logger(
    save_logging_messages=True,
    display_logging_messages=True,
)

for link_room_id in link_room_id_list:
    logger.info(link_room_id)

    download(
        path=path,
        login_url=login_url,
        zfn_user=zfn_user,
        zfn_password=zfn_password,
        logger=logger,
        link_room_id=link_room_id,
    )
    logger.info("Download done")
    process(
        path=path,
        time_start=time_start,
        time_end=time_end,
        nextcloud_url=nextcloud_url,
        nextcloud_app_user=nextcloud_app_user,
        nextcloud_app_password=nextcloud_app_password,
        studip_room_name=studip_room_name,
        studip_start=studip_start,
        studip_end=studip_end,
        studip_description=studip_description,
        studip_person=studip_person,
        logger=logger,
    )
    logger.info("Processing done")

Path(os.path.join(working_dir, "DONE")).touch()
