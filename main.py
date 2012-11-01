#
# DepressionGraph.com
# Author: Allan Kenneth <hello@allankenneth.com>
#

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

# 
class Inventories(db.Model):
    user = db.UserProperty()
    date = db.DateTimeProperty(auto_now_add=True)
    answers = db.ListProperty(long)
    dsmscore = db.IntegerProperty()
    score = db.IntegerProperty()

# This is to track whether a reminder has been set yet, or not.
# When you initate a test, we select all reminders here filtered 
# for your user; if there's already a reminder here, then we 
# delete the reminder and remove it from the task queue.
# When you submit an inventory, it will add the reminder here and 
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
                graph.append([graphdate,test.score,test.key()])

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
            
            tabled = []
            for test in inventories:
                #tabledate = test.date.strftime("%b %d %Y")
                tabledate = test.date
                tabled.append([tabledate,test.score,test.key()])
            tabled.reverse()
            url = users.create_logout_url(self.request.uri)
            url_linktext = 'Logout'
            template_values = {
                'userreg': userreg,
                'message': 'Your Library',
                'table': tabled,
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
                diagnoses = self.diagnose(inventory[0].score)
                yeahdate = inventory[0].date.strftime("%a, %d %b %Y")
                template_values = {
                    'reminderset': self.request.get('reminderset'),
                    'emailsent': self.request.get('emailsent'),
                    'date': yeahdate,
                    'diagnoses': diagnoses,
                    'score': inventory[0].score,
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
              answers.append('<span class="badge">0</span> - At no time.')
          if ans == 1:
              answers.append('<span class="badge">1</span> - Some of the time.')
          if ans == 2:
              answers.append('<span class="badge">2</span> - Slightly less than half the time.')
          if ans == 3:
              answers.append('<span class="badge">3</span> - Slightly more than half the time.')
          if ans == 4:
              answers.append('<span class="badge">4</span> - Most of the time.')
          if ans == 5:
              answers.append('<span class="badge">5</span> - All of the time.')
        
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

        reminder_query = Reminders.all()
        reminder_query.filter("user", user)
        reminder = reminder_query.fetch(10)
        reminddate = ''
        if reminder:
            reminddate = reminder[0].date.strftime("%a, %b. %d")
        
        template_values = {
            'reminddate': reminddate,
            'message': 'Log an Inventory',
            'useremail': useremail
        }
        path = os.path.join(os.path.dirname(__file__), 'views/inventory-form.html')
        self.response.out.write(template.render(path, template_values))

    def post(self):
        """
        The inventory test form gets posted here.
        """
        user = users.get_current_user()
        if user:    
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
            #
            # Create a list with all answer values in the order presented; 
            # this is what gets written to the datastore as a receipt of the 
            # inventory; we do the actual score calculation below in the 
            # ScoreInventory method
            #
            # TODO Instead of manually int'ing these values, do it properly?
            # i.e. results = map(int, results)
            #
            answers = [int(low[0]),
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
            totalscore = self.ScoreInventory(answers)
            entry = Inventories()
            entry.user = user
            entry.answers = answers
            entry.score = totalscore
            entry.put()
            entrykey = str(entry.key())
            remind = ''
            if self.request.get('reminder'):

                remind = 1

                # Check to see if there's already a reminder set,
                # and delete it if it's there.
                # TODO Don't delete it! Just update it with the new date!
                # DUH.
                reminder_query = Reminders.all()
                reminder_query.filter("user", user)
                reminder = reminder_query.fetch(10)
                if reminder:
                    # first remove from datastore
                    remdel = reminder[0].key()
                    db.delete(remdel)
                    # then remove from taskqueue
                    name = str(reminder[0].date)
                    name = md5.md5(name).hexdigest()
                    q = taskqueue.Queue('default')
                    q.delete_tasks(taskqueue.Task(name=name))

                now = datetime.datetime.now()
                twoweeks = timedelta(days=14)
                remindin = now + twoweeks
                
                addalarm = Reminders()
                addalarm.user = user
                addalarm.date = remindin
                addalarm.put()
                remindkey = addalarm.key()
                
                # 2 weeks = 1 209 600 seconds
                parameters = {'emailto': self.request.get('remindemail'), 'key': remindkey}

                name = str(remindin)
                name = md5.md5(name).hexdigest()
                taskqueue.add(name=name, url='/reminder', countdown=1209600, params=parameters)
            
            action = '/inventory?iid=' + entrykey + '&reminderset=' + str(remind)
            self.redirect(action)

    def ScoreInventory(self,answers):
        """

        """
        # Compare 8a with 8b and note the highest value as a variable.
        if answers[7] > answers[8]:
          eight = answers[7]
        else:
          eight = answers[8]
        # Do the same as above for 10a & 10b
        if answers[10] > answers[11]:
          ten = answers[10]
        else:
          ten = answers[11]
        # Now we need to remove answers 8a, 8b & 10a, 10b
        shortlist = list(answers)
        shortlist.pop(7)
        shortlist.pop(7)
        shortlist.pop(8)
        shortlist.pop(8)
        # Now we loop through and add up scores minus 8ab/10ab
        score = 0
        for ans in shortlist:
          score = score + ans
        # Finally we add in the highest scores from 8 & 10.
        # For DSM, we'd need to accommodate the hightest of 4 & 5.
        totalscore = score + eight + ten

        return totalscore

        

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
        """


        """

        k = db.Key(self.request.get('iid'))
        inventory_query = Inventories.all()
        inventory_query.filter('__key__ =', k)
        inv = inventory_query.fetch(1)

        answers = Inventory().scoreit(inv[0].answers)
        diagnoses = Inventory().diagnose(inv[0].score)
        
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

        #
        # TODO Update plain text version so it's better and shows everything 
        # the HTML version does.
        #
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
             inv[0].score,
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
             inv[0].score,
             diagnoses)
                     
        message.send()
        action = '/inventory?iid=' + self.request.get('iid') + '&emailsent=1'
        self.redirect(action)
#         else:
#             action = '/'
#             self.redirect(action) 


class UpdateScores(webapp.RequestHandler):


    def get(self):
        """
        We updated the datastore to move from 'dsmscore' to
        simply 'score' so we needed to copy over the dsmscores from 
        older tests so that they're still usable.
        """
        if users.is_current_user_admin():
            inventories_query = Inventories.all()
            inventories = inventories_query.fetch(1000)
            for inv in inventories:
                k = db.get(inv.key())
                k.score = inv.dsmscore
                k.put()
                g = '(score:' + str(inv.score) + ' - dsmscore: ' + str(inv.dsmscore) + ')\n'
                self.response.out.write(g)
            self.response.out.write("Done")


class ReScore(webapp.RequestHandler):


    def get(self):
        """
        Occasionally we'll fuck up and accidentally delete all the tallied scores 
        in the datastore (using above UpdateScores), and we'll need to re-score
        them based on the recorded answers.
        """
        if users.is_current_user_admin():
            inventories_query = Inventories.all()
            inventories = inventories_query.fetch(1000)
            for inv in inventories:
                ti = TakeInventory()
                newscore = ti.ScoreInventory(inv.answers)
                k = db.get(inv.key())
                k.score = newscore
                k.dsmscore = newscore
                k.put()
                g = 'score: ' + str(newscore) + '<br>'
                self.response.out.write(g)
            self.response.out.write("Done.")


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
                                      ('/updatescores', UpdateScores),
                                      ('/rescore', ReScore),
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