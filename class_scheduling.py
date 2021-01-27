import datetime
import random
import ezgmail

class ScheduledPerson:

    def __init__(self, msgmatrix, contact):
        """
        :param msgmatrix: the messages that will be sent
        :param contact: the contact info of the individual
        """

        # Identification
        self.msgmatrix = msgmatrix
        self.contact = contact

        # Scheduler based

        self.fm = datetime.datetime.now()

        self.time_list = []
        self.time_dict = {}

    def random_interval_calc(self, duration, min, max):

        """
        :param duration: length of time
        :param min: minimum value for the increment
        :param max: maximum value for the increment
        """
        
        lm = self.fm + datetime.timedelta(minutes=duration)
        new_time = self.fm
        time_list = []
        while new_time < lm:
            time_list.append(new_time)
            increment = random.randint(min, max)
            new_time += datetime.timedelta(minutes=increment)

        self.time_list = time_list

    def interval_calc(self, duration, increment):
        lm = self.fm + datetime.timedelta(minutes=duration)
        new_time = self.fm
        time_list = []
        while new_time < lm:
            time_list.append(new_time)
            new_time += datetime.timedelta(minutes=increment)

        self.time_list = time_list
        
    def time_assembler(self):
        time_dict = {}
        identifier = 0
        for time in self.time_list:
            try:
                time_dict[time] = self.msgmatrix[identifier]
            except IndexError:
                identifier = 0
                time_dict[time] = self.msgmatrix[identifier]
            identifier += 1


        self.time_dict = time_dict

    def random_time_assembler(self):
        time_dict = {}
        for time in self.time_list:
            try:
                identifier = random.randint(0, len(self.msgmatrix) - 1)
            except ValueError:
                identifier = 0
            time_dict[time] = self.msgmatrix[identifier]

        self.time_dict = time_dict

    def send_message(self, msg):
        ezgmail.send(self.contact, subject='', body=msg)

    def message_scheduler(self):
        for time, msg in self.time_dict.items():
            mainsched.add_job(self.send_message, 'date', run_date=time, args=msg, misfire_grace_time=500)

    def operate_scheduler(self, duration, increment):
        self.interval_calc(duration, increment)
        self.time_assembler()
        #self.message_scheduler()

    def random_operate_scheduler(self, duration, min, max):
        self.random_interval_calc(duration, min, max)
        self.random_time_assembler()
        self.message_scheduler()
