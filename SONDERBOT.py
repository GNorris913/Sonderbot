#!/bin/env/python3
#SONDERBOT - (C) Greg Norris 2019-2020
#Simple SSL-IRC Chat Bot
#from IRCCON import *
#### BOTCLIENT(server, port,channel,botnick,botnick2,botnick3,botnickpass,botpass)


###### PROGRAM STRUCTURE ######
#   dotenv file required ".env", see "sample.env" file for reference.
#
#   IRCCON - handles the IRC connection to the IRC server.
#       -Contains: connect, joinChannel, send, get_response, get_names, whisper
#
#   BOTCLIENT: Contains bot functions, commands list, addons, main event loop.
#       -Creates IRCCON class.
#       -All command scripts rely on Messages:(Channel, User, Message) input
#       -All command scripts have return functions: to_channel[Messages], and to_user[Messages]
#
#   WORKING FUNCTIONS: (default trigger is: "!")
#       Count Fucks
#           -Counts the number of times each user has said the word "fuck",
#               -returns leader-board of top 5 users with highest score
#
#   FUNCTIONS IN PROGRESS:
#       All addons are initialized in the array appList[] as their own class items.
#       Addons are called sequentially from the array and have input(), to_channel(), to_user invoked().
#
#       SPYFALL: (Addon)
#           Start Spyfall
#               -Social deduction game, all players except the spy know the location, only the spy knows they are the spy.
#               -Input(message), Output: to_channel, to_player
#           Stop Spyfall
#               -Stop the Spyfall game
#       GREEN GLASS DOOR: (Addon)
#           Start Green Glass Door
#               -Word game which asks players to choose an item to pass through the door.
#               -Input(message), Output: to_channel, to_player


import logging
from CountFucks import *
from scripts.game_spyfall import * # text+IRC--> Spyfall() --> IRC.send()
from scripts.game_trivia import *  # text+IRC--> Spyfall() --> IRC.send()
from spyfall2 import *
from DungeonGrenGlasRom import *
from dotenv import load_dotenv

##########################################
# IRCCON -> BOTCLIENT -> (MESSAGE{user:, message:}) -> Commands -> (sendout[])
##########################################
class IRCCON:
    irc = socket.socket()
    read_buffer = ""
    server = ""
    port = ""
    botnick = ""
    botnick2 = ""
    botnick3= ""
    botnickpass = ""
    channel = ""
    channelList = {}
    users = []
    RPL_NAMESREPLY = '353'
    RPL_ENDOFNAMES = '366'

    def __init__(self):
        self.irc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.irc = ssl.wrap_socket(self.irc)
        self.irc.setblocking(True)

    def connect(self, server, port, botnick, botnick2, botnick3, botpass, botnickpass):
        self.server = server
        self.port = port
        self.botnick = botnick
        self.botnick2 = botnick2
        self.botnick3 = botnick3
        self.botpass = botpass
        self.botnickpass = botnickpass

        #connect to server
        print("connecting to: " + server)
        self.irc.connect((server, port))

        #Authenticate User
        self.irc.send(bytes("PASS spyfall \n", "UTF-8"))
        #User authentication
        self.irc.send(bytes("USER " + botnick + " " + botnick + " " + botnick + " :SonderBot\n", "UTF-8"))
        self.irc.send(bytes("NICK " + botnick + "\n", "UTF-8"))
        #self.irc.send(bytes("NICKSERV IDENTIFY " + botnickpass + " " + botpass + "\n", "UTF-8"))
        time.sleep(2)

        #self.irc.send(bytes("JOIN " + channel + "n", "UTF-8"))

    def joinchannel(self, channel):
        self.irc.send(bytes("JOIN "+channel+"\n", "UTF-8"))

    def send(self, channel, msg):
        self.irc.send(bytes("PRIVMSG " + channel + " " + msg + "\n", "UTF-8"))

    def whisper(self, channel, user, msg):
        channel = channel[1:]
        user = user[1:]
        print(channel + " " + user)
        # self.irc.send(bytes("PRIVMSG " + channel + ':/msg ' + user + " " + msg + "\n", "UTF-8"))
        print("PRIVMSG #" + channel + ' :/msg ' + user + " " + msg + "\r\n")
        self.irc.send(bytes("PRIVMSG " + user + " :" + msg + "\r\n", "UTF-8"))

    def echo(self,channel,user,msg):
        channel = channel[1:]
        user = user[1:]

    def get_response(self):
        time.sleep(.1)
        response = ""
        try:
            response = self.irc.recv(4096).decode("UTF-8")   #2040
            if response.find('PING') != -1:
                self.irc.send(bytes('PONG ' + response.split()[1].encode('UTF-8').decode('UTF-8') + '\r\n', "UTF-8"))
                #self.irc.send(bytes("PONG", "UTF-8"))
                print("RESPONSE"+response)

        except Exception as ex:
            print(ex)
        return response

    def get_names(self, in_channel, firstRun):
        gotNames = False
        if firstRun == False:
            self.irc.send(bytes('NAMES ' + in_channel + '\r\n', "UTF-8"))
        while gotNames == False:
            time.sleep(.3)
            self.read_buffer += self.get_response()
            lines = self.read_buffer.split('\r\n')
            self.read_buffer = lines.pop()
            print(self.read_buffer)
            for line in lines:
                response = line.rstrip().split(' ', 3)
                response_code = response[1]
                if response_code == self.RPL_NAMESREPLY:
                    names_list = response[3].split(':')[1]
                    print(names_list)
                    self.users += names_list.split(' ')
                if response_code == self.RPL_ENDOFNAMES:
                    gotNames = True
        return self.users

#############################################################################
#                                BOTCLIENT                                  #
#############################################################################
class BOTCLIENT:
#### BOTCLIENT(port,channel,botnick,botnick2,botnick3,botnickpass,botpass) ####
    ##IRC CONFIG###
    botRunning = True
    gameEnabled = False
    spyfallEnabled = False
    triviaEnabled = False
    pottymouth = False
    starttime = 0
    trigger = "!"
    irc = IRCCON()
    accessList = {}
    cwd = ""
    users = []
    channelQueue = []
    whisperQueue = []
    channelList = {}
    appsList = {}

    def __init__(self,
                 server,
                 port,
                 channel, botnick, botnick2, botnick3, botnickpasswd, trigger):

        #Accepts connection parameters from .env, can be set manually here
        self.server = server
        self.port = port
        self.channel = channel
        self.botnick = botnick
        self.botnick2 = botnick2
        self.botnick3 = botnick3
        self.botnickpass = botnickpasswd
        self.botpass = " "
        self.gameEnabled = False
        self.spyfallEnabled = False
        self.triviaEnabled = False
        self.spyfall = SpyFall(self.irc)
        self.channelsList = []
        self.trigger = trigger
        #self.functions.add[commands]

        #initiate IRC connection
        self.irc.connect(self.server, self.port, self.botnick,
                         self.botnick2, self.botnick3, self.botpass, self.botnickpass)
        self.irc.joinchannel(self.channel)
        self.cwd = os.getcwd()
        self.users = self.irc.get_names(self.channel, True)
        
        #############################################################################
        self.bot_running()  # MAIN EVENT LOOP
        #############################################################################

    def bot_running(self):
        magic_character = "!"
        trigger = magic_character

#*************** MAIN EVENT LOOP ****************************
        while self.botRunning:
            t = self.irc.get_response()
            #prints chat text to window
            print(t)
            self.commands(t)
            self.speak("I LIVE!")


###### CMDs ########
    def commands(self, text):
        commands_dispatch = {
            self.trigger+"fuck": self.outputFuck,
            self.trigger+"count fucks": self.count_fucks,
            self.trigger+"start spyfall": self.start_spyfall,
            self.trigger+"stop spyfall": self.stop_spyfall,
            self.trigger+"shutdown": self.shutdown,
            self.trigger+"fuck everyone": self.count_fucks,
            self.trigger+"join channel": self.joinChannel(text),

        }
        user = re.match(':.*?!', text)
        if user:
            user = user.group(0)
            user = user[1:-1]

            botName = re.match(self.botnick, user)
            if botName:
                pass
            else:
                command = re.search(r':.*?:', text) #isolate command in text
                channel = re.search(r'#.*?:', text) #isolate channel in text
                if channel:
                    channel = str(text[len(channel.group(0)):]).lower()
                else:
                    channel = "#botspam"
                    print("CHANNEL NOT FOUND")

                if command:
                    command = str(text[len(command.group(0)):]).lower()
                    message = {"user": user, "channel": channel, "command": command}
                    for key in commands_dispatch:
                        if key in command:
                            print("COMMAND FOUND")
                            print(user+" "+channel+" "+command)

                            ############### DISPATCH #####################
                            commands_dispatch[key](message)
                            break
                    self.addons(message)


    def addons(self, *message):
        for app in self.appsList:
            self.appsList[app].input(message)
            channelout = self.appsList[app].to_channel()
            whispers = self.appsList[app].to_user()
            if whispers:
                for whisper in whispers:
                    self.whisperQueue.append(whisper)
            if channelout:
                for message in channelout:
                    self.channelQueue.append(message)

    def speak(self, in_channel):
        for message in self.channelQueue:
            self.irc.send(in_channel, message)
        for whisper in self.whisperQueue:
            self.irc.whisper(in_channel, whisper[0], whisper[1])

        self.channelQueue.clear()
        self.whisperQueue.clear()

    def acl(self, username, permission):
        access = False
        accessControlList = {"Sonder": 69, "rachel": 69}
        if username in accessControlList:
            access = True
        return access

    def start_spyfall(self):
        #self.irc.send(self.channel, "Spyfall Started")
        self.appsList["sf"] = SpyFall(self.trigger)
        print("Spyfall Started")

    def shutdown(self):
        self.botRunning = False

    def stop_spyfall(self):
        #self.irc.send(self.channel, "Spyfall Started")
        print("Spyfall Stopped")

    def stop(self):
        self.irc.send(self.channel, "Make Me")
        print("Make me")
    def echo(self):
        print("Echo ... ... ... echo")
    def no_echo(self):
        pass

    def count_fucks(self, *fuckingMessage):
        #print("counting fucks")
        cf = CountFucks()
        leaderboard = cf.returnfucks()
        for fuckers in leaderboard:
            #self.irc.send(self.channel, fuckers)
            self.channelQueue.append(fuckers)

    def outputFuck(self, channel, user, message):
        self.irc.send(self.channel, "Fuck")

    def joinChannel(self, text):
        #TODO - confirm ACL, IRCCON.joinChannel(), add to channels list
        pass

###########################    MAIN    ############################################
def main():
    try:
        #Load default connection perameters from .env
        load_dotenv()
        LOG = os.getenv("SONDERBOT_LOGS")
        BOTNICK = os.getenv("SONDERBOT_BOTNICK")
        BOTNICK2 = os.getenv("SONDERBOT_BOTNICK2")
        BOTNICK3 = os.getenv("SONDERBOT_BOTNICK3")
        CHANNEL = os.getenv("SONDERBOT_CHANNEL")
        TRIGGER = os.getenv("SONDERBOT_ACL")
        SERVER = os.getenv("SONDERBOT_TRIGGER")
        PORT = os.getenv("SONDERBOT_SERVER")
        CHANNEL = os.getenv("SONDERBOT_PORT")
        BOTNICKPASSWD = os.getenv("SONDERBOT_BOTNICKPASSWD")

        bot = BOTCLIENT(SERVER, PORT, CHANNEL, BOTNICK,
                        BOTNICK2, BOTNICK3, BOTNICKPASSWD, TRIGGER)
    except Exception as e:
        print(e)
        pass


###############
if __name__ == '__main__':
    main()
###########################    MAIN    ############################################

#TODO - LOGGING
#class Logger():
#    logger = logging.getLogger('SONDERBOT')
#    hdlr = logging.FileHandler