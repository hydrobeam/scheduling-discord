# scheduling-discord

## A discord bot used to send reminders to yourself via  email
Can also be configured to email to SMS using an SMS gateway depending on the carrier. i.e. for Bell (Canada): 4161231234@txt.bell.ca 
[Attached is a list of SMS gateways depending on carrier](https://smsemailgateway.com/)

## Explanation of triggers
#### Date
- The date trigger sets a task for a specific time
    - *Task for Today 9:08pm, Task for Feb 2 10:00am*
    
#### Cron
- The cron trigger schedules a repeating task that sends a message at a specific time
    - *Task for Every Friday 12:00am, Task for 7:00am every day*
    

#### Interval
- Sends a message 

### Sample input

> **/date-message**: Setting a reminder for a specific date/time
![img_1.png](https://github.com/hydrobeam/scheduling-discord/blob/main/img_1.png)
  
> **/get-schedule**: Get a list of scheduled tasks
![img.png](https://github.com/hydrobeam/scheduling-discord/blob/main/img.png)
### uses mongodb, gmail api and apscheduler to store, send and schedule messages
