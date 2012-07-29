#!/usr/bin/env python
#
# MAJOR DEPRESSION INVENTORY - DepressionGraph.com
# Author: Allan Haggett

import os
import md5
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from google.appengine.api import taskqueue
from google.appengine.ext import webapp
from google.appengine.api import users
from google.appengine.api import mail
from google.appengine.ext import db

import datetime
from time import gmtime, strftime
from datetime import date
from datetime import timedelta

class Inventories(db.Model):
    user = db.UserProperty()
    date = db.DateTimeProperty(auto_now_add=True)
    answers = db.ListProperty(long)
    dsmscore = db.IntegerProperty()

# This is to track whether a reminder has been set yet, or not.
# When you initate a test, we select all reminders here filtered 
# for your user; if there's already a reminder here, then we 
# delete the reminder and remove it from the task queue.
# When you take an inventory, it will add the reminder here and 
# into the task queue with the new countdown
class Reminders(db.Model):
    user = db.UserProperty()
    date = db.DateTimeProperty()
    


class MainHandler(webapp.RequestHandler):


    def get(self):
        user = users.get_current_user()
        if user:
            userreg = user.nickname()
            inventories_query = Inventories.all()
            inventories_query.filter("user", user)
            inventories_query.order("date")
            inventories = inventories_query.fetch(100)
            
            reminder_query = Reminders.all()
            reminder_query.filter("user", user)
            reminder = reminder_query.fetch(10)
            
            graph = []
            tabled = []
            for test in inventories:
                graphdate = test.date.strftime("%b %d")
                graph.append([graphdate,test.dsmscore,test.key()])
                tabledate = test.date.strftime("%b %d %Y")
                tabled.append([tabledate,test.dsmscore,test.key()])
            tabled.reverse()
            url = users.create_logout_url(self.request.uri)
            url_linktext = 'Logout'
            template_values = {
                'userreg': userreg,
                'message': 'Your Library',
                'graph': graph,
                'table': tabled,
                'reminder': reminder,
                'url': url,
                'url_linktext': url_linktext
            }
            path = os.path.join(os.path.dirname(__file__), 'views/index.html')
            self.response.out.write(template.render(path, template_values))
#             self.response.out.write(graph.date)
        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login'
            template_values = {
                'url': url,
                'url_linktext': url_linktext,
                'message': 'Welcome'
            }
            path = os.path.join(os.path.dirname(__file__), 'views/login.html')
            self.response.out.write(template.render(path, template_values))

class Inventory(webapp.RequestHandler):


    def get(self):
        user = users.get_current_user()
        if user:
            if(self.request.get('action') == "delete"):
                user = users.get_current_user()
                k = db.Key(self.request.get('iid'))
                db.delete(k)
                action = '/'
                self.redirect(action)
            else:

                userreg = user.email()
                k = db.Key(self.request.get('iid'))
                inventory_query = Inventories.all()
                inventory_query.filter('__key__ =', k)
                inventory = inventory_query.fetch(1)
                # TODO the following should be broken out into its own method(s)
                answers = []
                for ans in inventory[0].answers:
                  if ans == 0:
                      answers.append("At no time (0).")
                  if ans == 1:
                      answers.append("Some of the time (1).")
                  if ans == 2:
                      answers.append("Slightly less than half the time (2).")
                  if ans == 3:
                      answers.append("Slightly more than half the time (3).")
                  if ans == 4:
                      answers.append("Most of the time (4).")
                  if ans == 5:
                      answers.append("All of the time (5).")
                if inventory[0].dsmscore <= 19:
                    diagnoses = "Not depressed."
                if inventory[0].dsmscore > 19:
                    diagnoses = "Mildly depressed."
                if inventory[0].dsmscore > 24:
                    diagnoses = "Moderately depressed."
                if inventory[0].dsmscore > 29:
                    diagnoses = "Severely depressed."
                
                yeahdate = inventory[0].date.strftime("%a, %d %b %Y")
                template_values = {
                    'reminderset': self.request.get('reminderset'),
                    'date': yeahdate,
                    'diagnoses': diagnoses,
                    'score': inventory[0].dsmscore,
                    'answer': answers,
                    'iid': self.request.get('iid')
                }
                path = os.path.join(os.path.dirname(__file__), 'views/inventory-complete.html')
                self.response.out.write(template.render(path, template_values))
        else:
            action = '/'
            self.redirect(action)
            
    def post(self):
        user = users.get_current_user()
        if user:
            self.response.out.write("We don't have a post action for this yet.")
        else:
            action = '/'
            self.redirect(action)
            
       
class TakeInventory(webapp.RequestHandler):


    def get(self):
    
        # TODO Check to see if there is an appointment scheduled; 
        # If there is, cancel it.
        
        user = users.get_current_user()
        if user:
            useremail = user.email()
            
        else:
            useremail = ''
        
        template_values = {
            'message': 'Log an Inventory',
            'useremail': useremail
        }
        path = os.path.join(os.path.dirname(__file__), 'views/inventory-form.html')
        self.response.out.write(template.render(path, template_values))

    def post(self):
    
        user = users.get_current_user()
        low = self.request.get_all('low-spirits')
        lost = self.request.get_all('lost-interest')
        lacking = self.request.get_all('lacking-energy')
        less = self.request.get_all('less-self-confident')
        bad = self.request.get_all('bad-conscience')
        worth = self.request.get_all('not-worth-living')
        difficult = self.request.get_all('difficulty-concentrating')
        restless = self.request.get_all('very-restless')
        subdued = self.request.get_all('subdued-or-slowed')
        sleeping = self.request.get_all('trouble-sleeping')
        reduced = self.request.get_all('reduced-appetite')
        increased = self.request.get_all('increased-appetite')
        # for logging purposes, create a list with all answer values
        # in the order presented; this is what gets written to the datastore
        # as a receipt of the inventory; we do the actual DSMIV score calculation
        # as below.
        allanswers = [int(low[0]),
                   int(lost[0]),
                   int(lacking[0]),
                   int(less[0]),
                   int(bad[0]),
                   int(worth[0]),
                   int(difficult[0]),
                   int(restless[0]),
                   int(subdued[0]),
                   int(sleeping[0]),
                   int(reduced[0]),
                   int(increased[0])]
        # create the initial list minus answers 8a/b & 10a/b
        answers = [int(low[0]),
                   int(lost[0]),
                   int(lacking[0]),
                   int(less[0]),
                   int(bad[0]),
                   int(worth[0]),
                   int(difficult[0]),
                   int(sleeping[0])]
        # we compare 8a with 8b and note the highest value as a variable
        if int(restless[0]) > int(subdued[0]):
          eight = int(restless[0])
        else:
          eight = int(subdued[0])
        # we do the same as above for 10a & 10b
        if reduced[0] > increased[0]:
          ten = int(reduced[0])
        else:
          ten = int(increased[0])
        #now we loop through and add up all scores
        score = 0
        for ans in answers:
          score = score + ans
        # finally we add in the highest scores from 8 & 10
        totalscore = score + eight + ten
        entry = Inventories()
        entry.user = user
        entry.answers = allanswers
        entry.dsmscore = totalscore
        entry.put()
        remind = 0
        if self.request.get('reminder'):
            # 2 weeks = 1 209 600 seconds
            parameters = {'emailto': self.request.get('remindemail')}
            now = datetime.datetime.now()
            twoweeks = timedelta(days=14)
            remindin = now + twoweeks
            name = str(remindin)
            name = md5.md5(name).hexdigest()
            taskqueue.add(name=name, url='/reminder', countdown=1209600, params=parameters)
            remind = 1
            alarm = Reminders()
            alarm.user = user
            alarm.date = remindin
            alarm.put()
        
        action = '/inventory?iid=' + str(entry.key()) + '&reminderset=' + str(remind)
        self.redirect(action)
        

class RemindersHandler(webapp.RequestHandler):

    def get(self):
        user = users.get_current_user()
        if user:
            if(self.request.get('action') == "delete"):
                k = db.Key(self.request.get('key'))
                getname = Reminders.all()
                getname.filter('__key__ =', k)
                name = getname.fetch(1)
                name = str(name[0].date)
                name = md5.md5(name).hexdigest()
                q = taskqueue.Queue('default')
                q.delete_tasks(taskqueue.Task(name=name))
                db.delete(k)
                self.redirect('/');
            else:
                self.response.out.write("Whatwhat!?")
    
    def post(self): 
        inventoryFrom = "allan@hitchless.com"
        inventorySubject = "Take Your Major Depression Inventory"
        message = mail.EmailMessage(sender=inventoryFrom,
                                    subject=inventorySubject)                     
        message.to = self.request.get('emailto')
        message.body = """Take an inventory: http://depressiongraph.appspot.com"""
        message.send()
        self.response.out.write("sent")

class InventoryEmail(webapp.RequestHandler):


    def post(self):

        k = db.Key(self.request.get('iid'))
        inventory_query = Inventories.all()
        inventory_query.filter('__key__ =', k)
        inventory = inventory_query.fetch(1)
        # TODO the following should be broken out into its own method(s)
        answers = []
        for ans in inventory[0].answers:
          if ans == 0:
              answers.append("0 - At no time.")
          if ans == 1:
              answers.append("1 - Some of the time.")
          if ans == 2:
              answers.append("2 - Slightly less than half the time.")
          if ans == 3:
              answers.append("3 - Slightly more than half the time.")
          if ans == 4:
              answers.append("4 - Most of the time.")
          if ans == 5:
              answers.append("5 - All of the time.")
        if inventory[0].dsmscore <= 19:
          diagnoses = "Not depressed."
        if inventory[0].dsmscore > 19:
          diagnoses = "Mildly depressed."
        if inventory[0].dsmscore > 24:
          diagnoses = "Moderately depressed."
        if inventory[0].dsmscore > 29:
          diagnoses = "Severely depressed."
        user = users.get_current_user()
        if user:
            inventoryFrom = user.email()
            inventoryNickname = user.nickname()
        else:
            inventoryFrom = "allan@hitchless.com"
            inventoryNickname = "Depression Graph"
            
        inventorySubject = "Major Depression Inventory from " + inventoryNickname
        message = mail.EmailMessage(sender=inventoryFrom,
                                    subject=inventorySubject)
        message.to = self.request.get('emailto')
        message.body = """Have you felt low in spirits or sad ?
%s
Have you lost interest in your daily activities ?
%s
Have you felt lacking in energy and strength?
%s
Have you felt less self-confident?
%s
Have you had a bad conscience or feelings of guilt?
%s
Have you felt that life wasn't worth living?
%s
Have you had difficulty in concentrating?
%s
Have you felt very restless?
%s
Have you felt subdued or slowed down?
%s
Have you had trouble sleeping at night?
%s
Have you suffered from reduced appetite?
%s
Have you suffered from increased appetite?
%s
Score
%s
Diagnoses
%s
"""     %   (answers[0],
             answers[1],
             answers[2],
             answers[3],
             answers[4],
             answers[5],
             answers[6],
             answers[7],
             answers[8],
             answers[9],
             answers[10],
             answers[11],
             inventory[0].dsmscore,
             diagnoses)
        
        message.send()
        action = '/inventory?iid=' + self.request.get('iid')
        self.redirect(action)
#         else:
#             action = '/'
#             self.redirect(action) 

class MoreInfo(webapp.RequestHandler):


    def get(self):
        path = os.path.join(os.path.dirname(__file__), 'views/info.html')
        self.response.out.write(template.render(path, {}))


application = webapp.WSGIApplication([('/', MainHandler),
                                      ('/inventory', Inventory),
                                      ('/take', TakeInventory),
                                      ('/info', MoreInfo),
                                      ('/reminders', RemindersHandler),
                                      ('/inventory-email', InventoryEmail)],
                                      debug=True)
def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()