# Zendesk away mode automation
This code uses Google Calendar API and Zendesk's API.

## Steps:
1. Check Google Calendar for events

![calendar](/public/calendar.png)

2. Get tickets with open status from Zendesk

3. Compare the 2 lists. If match -> move tickets to "general tier" group and add note
![result](/public/result.png)


## notes
Follow [Google calendar's quick start instructions](https://developers.google.com/calendar/api/quickstart/python) to gain access to your calendar.
You will need to use your token.json file from Google

![files](/public//files.png)