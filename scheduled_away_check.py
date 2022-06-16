from __future__ import print_function
import datetime
import os.path
import json
import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SPACER = "\n--------------------\n"
NUM_OF_EVENTS = 10 # num of events to pull from calendar
TIME_MAX_FILTER = 5
ZD_TOKEN = 'YOUR_ZENDESK_TOKEN'
CALENDAR_SECRET = 'calendar_secret.json'
TIER1_GROUP_ID = "ZD_GROUP_ID"
TEAM_MEMBERS = [] # Add your team members here

# --------------------------------------------------
# Google calendar API
# --------------------------------------------------
SCOPES = ['https://www.googleapis.com/auth/calendar.events'] # If modifying these scopes, delete the file token.json.
CALENDAR_TOPULL = "YOUR_CALENDAR_ID" # Support Team - Vacations and OOO

def format_events_list(event_list):
    """
    Helper function. takes the events from the calendar and returns just the first word as new list:
    ['Quinn', 'Shawn']
    """
    res = []
    for event in event_list:
            start = event['start'].get('dateTime', event['start'].get('date'))
            name_from_summary = event['summary'].split()[0]
            res.append(name_from_summary)
    return res
            

def get_events_from_support_calendar():
    """
    Google Calendar API - GET
    Returns formatted array of events like-
    ['Roy day shift @ 2022-06-06T16:00:00+03:00']
    """
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CALENDAR_SECRET, SCOPES)
            creds = flow.run_local_server(port=0)

    try:
        service = build('calendar', 'v3', credentials=creds)

        now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
        five_min =  (datetime.datetime.utcnow() + datetime.timedelta(minutes=TIME_MAX_FILTER)).isoformat() + 'Z'
        events_result = service.events().list(calendarId=CALENDAR_TOPULL, timeMin=now, timeMax=five_min,
                                              maxResults=NUM_OF_EVENTS, singleEvents=True,
                                              orderBy='startTime').execute()
        events = events_result.get('items', [])

        if not events:
            print('No upcoming events found.')
            return

        formatted_events = format_events_list(events)
        return formatted_events

    except HttpError as error:
        print('An error occurred: %s' % error)


# --------------------------------------------------
# Zendesk API
# --------------------------------------------------
def move_to_tier_1_unassigned(ticket_id, asignee):
    """
    ZendDesk API - PUT
    Moves ticket to tier1 queye (unassigned) & adds internal note
    """
    url = "https://{subdomain}.zendesk.com/api/v2/tickets/{}".format(ticket_id)

    comment_text = "{} is not available - Moving to tier 1 unassigned queue".format(asignee)
    payload = json.dumps({
        "ticket": {
            "assignee_id": None,
            "group_id": TIER1_GROUP_ID,
            "comment": {
                "body": comment_text,
                "public": False
            },
            "status": "open"
        }
    })
    headers = {
        'Authorization': ZD_TOKEN,
        'Content-Type': 'application/json'
    }
    response = requests.request("PUT", url, headers=headers, data=payload)
    print(response)


def sort_array_by_key(e): # Helper function to sort the zendesk tickets list
  return e["assignee_id"]

def get_open_tickets_from_zd(group_id):
    """
    ZendDesk API - GET
    Retrieves all tickets with status:open and for specific group_id 
    """
    url = "https://{subdomain}.zendesk.com/api/v2/search.json?query=type:ticket status:open" # GET ALL open tickets
    headers = {
    'Authorization': ZD_TOKEN
    }
    response = requests.request("GET", url, headers=headers, data={})
    res_json = response.json()
    results = res_json.get("results")

    final_ticket_arr = []
    for ticket in results:
        assignee_id = ticket.get("assignee_id")
        if assignee_id is not None:
            ticket_id = ticket.get("id")
            ticket_url = "https://{subdomain}.zendesk.com/agent/tickets/{}".format(ticket_id)
            ticket_to_add = {
                "assignee_id": assignee_id,
                "ticket_id": ticket_id,
                "ticket_url": ticket_url
            }
            final_ticket_arr.append(ticket_to_add)

    if len(final_ticket_arr) > 1:
        final_ticket_arr.sort(key=sort_array_by_key)
        return final_ticket_arr
    else:
        print("no tickets")


# --------------------------------------------------
# Comparison
# --------------------------------------------------

def compare_ticket_and_member(members, tickets):
    """
    compares filtered list of members list with open tickets list
    returns list of open tickets with members that are not on shift
    """
    tickets_to_update = []
    for ticket in tickets:
        assignee_id = str(ticket.get('assignee_id')) # assignee_id is int by default so we convert to str
        ticket_id = str(ticket.get('ticket_id'))
        
        for member in members:
            member_id = member.get('zendeskAgentID')
            assignee_name = member.get('supportEngineerName')
            if assignee_id == member_id:
                print('bingo! ticket {} is open but {} is OOO'.format(ticket_id, assignee_name))
                ticket_to_add = {
                    "ticket_id": ticket_id,
                    "assignee_name": assignee_name
                }
                tickets_to_update.append(ticket_to_add)
    if len(tickets_to_update) > 0:
        return tickets_to_update
    else:
        print('no tickets matched')

# --------------------------------------------------
# Run code
# -------------------------------------------------- 
def lambda_handler(event, context):
    print('{}members_on_calendar ------>\n'.format(SPACER))
    members_on_calendar = get_events_from_support_calendar()

    if(members_on_calendar == None):
        print("No one is on vacation right now. stopping")
    else:
        print(members_on_calendar)
        print("{}support_member_list ------>\n".format(SPACER))
        print(TEAM_MEMBERS)

        print("{}open_tickets_list ------>\n".format(SPACER))
        open_tickets_list = get_open_tickets_from_zd(TIER1_GROUP_ID)
        print(open_tickets_list)

        print("{}comparing ------>\n".format(SPACER))
        tickets_to_update = compare_ticket_and_member(TEAM_MEMBERS, open_tickets_list)
        print("\ntickets_to_update (open tickets with members that are not on shift atm):\n{}".format(tickets_to_update))

        if len(tickets_to_update) > 0:
            print('{}Moving tickets to tier 1 queue ------>\n'.format(SPACER))
            for ticket_to_move_to_tier_1 in tickets_to_update:
                ticket_id = ticket_to_move_to_tier_1.get('ticket_id')
                assignee_name =  ticket_to_move_to_tier_1.get('assignee_name')
                print("\nticket - {}".format(ticket_id))
                move_to_tier_1_unassigned(ticket_id, assignee_name)
        else:
            print("{}No tickets to move".format(SPACER))


# Test run
lambda_handler("test", "test")