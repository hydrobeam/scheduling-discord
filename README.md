# Scheduling-bot

## A discord bot used to send reminders to yourself via discord and slash commands!

## Explanation of triggers
#### Date
- The date trigger sets a task for a specific time
    - *Task for Today 9:08pm, Task for Feb 2 10:00am*
    
#### Cron
- The cron trigger schedules a repeating task that sends a message at a specific time
    - *Task for Every Friday 12:00am, Task for 7:00am every day*
    

#### Interval
- Sends a message and waits for a specific duration before repeating the message
  - *Task to send "break" every 30 minutes*

### Sample input

> **/date-message**: Setting a reminder for a specific date/time
![img_1](https://user-images.githubusercontent.com/70682032/106963691-f6a2ce80-670e-11eb-8b6a-31fe669b35e1.png)

> **/get-schedule**: Get a list of scheduled tasks
![img](https://user-images.githubusercontent.com/70682032/106963676-f30f4780-670e-11eb-8819-9b475512dbae.png)

### Scheduling-bot uses mongodb, and apscheduler to store, send and schedule messages
