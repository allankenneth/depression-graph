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
            for test in inventories:
                graphdate = test.date.strftime("%b %d")
                graph.append([graphdate,test.dsmscore,test.key()])

            url = users.create_logout_url(self.request.uri)
            url_linktext = 'Logout'
            template_values = {
                'userreg': userreg,
                'message': 'Your Library',
                'graph': graph,
                'reminder': reminder,
                'url': url,
                'url_linktext': url_linktext
            }
            path = os.path.join(os.path.dirname(__file__), 'views/index.html')
            self.response.out.write(template.render(path, template_values))

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


class ListInventories(webapp.RequestHandler):
    
    
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
            
            tabled = []
            for test in inventories:
                #tabledate = test.date.strftime("%b %d %Y")
                tabledate = test.date
                tabled.append([tabledate,test.dsmscore,test.key()])
            tabled.reverse()
            url = users.create_logout_url(self.request.uri)
            url_linktext = 'Logout'
            template_values = {
                'userreg': userreg,
                'message': 'Your Library',
                'table': tabled,
                'reminder': reminder,
                'url': url,
                'url_linktext': url_linktext
            }
            path = os.path.join(os.path.dirname(__file__), 'views/list.html')
            self.response.out.write(template.render(path, template_values))
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
                action = '/list'
                self.redirect(action)
            else:
                userreg = user.email()
                k = db.Key(self.request.get('iid'))
                inventory_query = Inventories.all()
                inventory_query.filter('__key__ =', k)
                inventory = inventory_query.fetch(1)
                answers = self.scoreit(inventory[0].answers)
                diagnoses = self.diagnose(inventory[0].dsmscore)
                yeahdate = inventory[0].date.strftime("%a, %d %b %Y")
                template_values = {
                    'reminderset': self.request.get('reminderset'),
                    'emailsent': self.request.get('emailsent'),
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
            
            
    def scoreit(self,scores):

        answers = []

        for ans in scores:
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
        
        return answers
        
    def diagnose(self,score):

        if score <= 19:
            diagnoses = "Not depressed."
        if score > 19:
            diagnoses = "Mildly depressed."
        if score > 24:
            diagnoses = "Moderately depressed."
        if score > 29:
            diagnoses = "Severely depressed."
            
        return diagnoses
       
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
        entrykey = str(entry.key())
        remind = 0
        if self.request.get('reminder'):
        
            # TODO check to see if there's already a reminder set,
            # and delete it if it's there.
            
            

            now = datetime.datetime.now()
            twoweeks = timedelta(days=14)
            remindin = now + twoweeks
            
            remind = 1
            alarm = Reminders()
            alarm.user = user
            alarm.date = remindin
            alarm.put()
            remindkey = alarm.key()
            
            # 2 weeks = 1 209 600 seconds
            parameters = {'emailto': self.request.get('remindemail'), 'key': remindkey}

            name = str(remindin)
            name = md5.md5(name).hexdigest()
            taskqueue.add(name=name, url='/reminder', countdown=1209600, params=parameters)

        
        action = '/inventory?iid=' + entrykey + '&reminderset=' + str(remind)
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
        
        k = db.Key(self.request.get('key'))
        db.delete(k)        
        
        self.response.out.write("sent")

class InventoryEmail(webapp.RequestHandler):


    def post(self):

        k = db.Key(self.request.get('iid'))
        inventory_query = Inventories.all()
        inventory_query.filter('__key__ =', k)
        inv = inventory_query.fetch(1)

        answers = Inventory().scoreit(inv[0].answers)
        diagnoses = Inventory().diagnose(inv[0].dsmscore)
        
        testdate = inv[0].date.strftime("%b %d %Y")

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

        message.body = """
Have you felt low in spirits or sad ?
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
             inv[0].dsmscore,
             diagnoses)
        message.html = """

<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Depression Graph Inventory</title>
</head>
<body style="font-family: Arial">
<h1>%s's Major Depression Inventory</h1>
<p>Taken: %s</p>
<table>
<tr>
<td width="360">
<h2>Answers</h2>
<p>Have you felt low in spirits or sad?<br>
<strong>%s</strong></p>
<p>Have you lost interest in your daily activities?<br>
<strong>%s</strong></p>
<p>Have you felt lacking in energy and strength?<br>
<strong>%s</strong></p>
<p>Have you felt less self-confident?<br>
<strong>%s</strong></p>
<p>Have you had a bad conscience or feelings of guilt?<br>
<strong>%s</strong></p>
<p>Have you felt that life wasn't worth living?<br>
<strong>%s</strong></p>
<p>Have you had difficulty in concentrating?<br>
<strong>%s</strong></p>
<p>Have you felt very restless?<br>
<strong>%s</strong></p>
<p>Have you felt subdued or slowed down?<br>
<strong>%s</strong></p>
<p>Have you had trouble sleeping at night?<br>
<strong>%s</strong></p>
<p>Have you suffered from reduced appetite?<br>
<strong>%s</strong></p>
<p>Have you suffered from increased appetite?<br>
<strong>%s</strong></p>
</td>
<td valign="top" style="text-align: center">
<p>
	Score<br>
	<strong style="font-size: 24px">%s</strong>
</p>
<p>
	Diagnoses<br>
	<strong style="font-size: 18px">%s</strong>
</p>
</td>
</tr>
</table>
</body>
</html>

"""     %   (inventoryNickname,
             testdate,
             answers[0],
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
             inv[0].dsmscore,
             diagnoses)
                     
        message.send()
        action = '/inventory?iid=' + self.request.get('iid') + '&emailsent=1'
        self.redirect(action)
#         else:
#             action = '/'
#             self.redirect(action) 

class MoreInfo(webapp.RequestHandler):


    def get(self):
        user = users.get_current_user()
        if user:
            userreg = user.nickname()
        else: 
            userreg = 0
        template_values = {
            'user': userreg,
        }
        path = os.path.join(os.path.dirname(__file__), 'views/info.html')
        self.response.out.write(template.render(path, template_values))

class Privacy(webapp.RequestHandler):
    
    
    def get(self):
        user = users.get_current_user()
        if user:
            userreg = user.nickname()
        else: 
            userreg = 0
        template_values = {
            'user': userreg,
        }
        path = os.path.join(os.path.dirname(__file__), 'views/privacy.html')
        self.response.out.write(template.render(path, template_values))

#        path = os.path.join(os.path.dirname(__file__), 'views/privacy.html')
#        self.response.out.write(template.render(path, {}))


application = webapp.WSGIApplication([('/', MainHandler),
                                      ('/list', ListInventories),
                                      ('/inventory', Inventory),
                                      ('/privacy', Privacy),
                                      ('/take', TakeInventory),
                                      ('/info', MoreInfo),
                                      ('/reminder', RemindersHandler),
                                      ('/inventory-email', InventoryEmail)],
                                      debug=True)
def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()