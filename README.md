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
![img](https://user-images.githubusercontent.com/70682032/106963676-f30f4780-670e-11eb-8819-9b475512dbae.png)
  
> **/get-schedule**: Get a list of scheduled tasks
![img_1](https://user-images.githubusercontent.com/70682032/106963691-f6a2ce80-670e-11eb-8b6a-31fe669b35e1.png)
### uses mongodb, gmail api and apscheduler to store, send and schedule messages
