import aiohttp
import asyncio
from threading import Thread

from .Events import Events
from .Errors import *
from .API_Elements import *
from .Voice import *
from .Gateway import *

class Utility:

	def get_self_user(self):
		return User(self.api("/users/@me", "GET"), self)

	def get_self_guilds(self):
		return [Guild(guild,self) for guild in self.api("/users/@me/guilds", "GET")]

	def send_message(self,channel,**kwargs):
		return Message(self.api(f"/channels/{channel}/messages", "POST", json=kwargs),self)

	def get_guild(self,guild_id):
		return Guild(self.api(f"/guilds/{guild_id}","GET"),self)

	def get_channel(self,channel_id):
		return Channel(self.api(f"/channels/{channel_id}","GET"),self)

	def get_user(self,user_id):
		return User(self.api(f"/users/{user_id}"), self)

	def get_invite(self, invite_code):
		return Invite(self.api(f"/invites/{invite_code}","GET", params={"with_counts":"true"}),self)

	def get_webhook(self, webhook_id):
		return Webhook(self.api(f"/webhooks/{webhook_id}"), self)

class Bot(Thread,Utility,Events):

	def __init__(self,token,api_sleep=0.05):
		self.events_list = {}
		Events.__init__(self)
		Thread.__init__(self)
		Utility.__init__(self)
		Bot_Element.__init__(self,{},self)
		self.token=token
		self.api_sleep = api_sleep
		self.api_url="https://discord.com/api"
		self.events = {}
		self.in_wait_voices = []
		self.presence = {"op": 3,"d": {"game":None,"status":None,"afk":False,"since":0}}
		self.gateway = None

	def def_event(self,event,name):
		def add_event(function):
			self.events_list[event] = [name,function]
			return
		return add_event

	def event(self,arg):

		def add_event(function):
			self.events[arg]=function
			return

		if type(arg) == str:
			return add_event

		self.events[arg.__name__] = arg
		return

	def get_element(self, element, **kwargs):
		try:
			for x in element:
				for a,b in kwargs.items():
					if not (a in x.__dict__ and str(x.__dict__[a]) == str(b)):
						break
				else:
					return x
			return
		except:...

	def set_element(self, element, new):
		try:
			for i in range(len(element)):
				if str(element[i].id) == str(new.id):
					element[i] = new
					return
		except:...

	async def api_call(self, path, method="GET", **kwargs):
		headers = {
			"Authorization": f"Bot {self.token}",
			"User-Agent": "Bot"
		}
		async with aiohttp.ClientSession() as session:
			async with session.request(method, self.api_url+path,headers = headers,**kwargs) as response:
				try:
					assert 200 <= response.status < 300
					if response.status in [200,201]:
						return await response.json()
				except:
					if response.status == 400:
						return BadRequestError()
					elif response.status == 403:
						return PermissionsError()
					else:
						return Error()

	def api(self, path, method="GET", **kwargs):
		loop = asyncio.new_event_loop()
		output = loop.run_until_complete(self.api_call(path,method,**kwargs))
		loop.run_until_complete(asyncio.sleep(self.api_sleep))
		loop.close()
		if output and isinstance(output,Error):
			raise output
		else:
			return output

	async def begin(self):
		response = await self.api_call("/gateway")
		await self.__main(response["url"])

	async def __main(self,url):
		events = self.events_list
		gateway = Gateway(f"{url}?v=7&encoding=json", self.token, presence=self.presence)
		self.gateway = gateway
		async for data in gateway.connect():
			if data["op"] == 0:
				if data["t"] in events:
					event = events[data["t"]]
					output = event[1](self,data["d"])
					if event[0] in self.events:
						x = Thread(target=self.events[event[0]],args=(output,))
						x.start()
			if self.in_wait_voices:
				for voice in self.in_wait_voices:
					if voice["guild_id"] not in self.voices:
						x = Voice(voice,self)
						self.voices[voice["guild_id"]] = x
						asyncio.create_task(x.run())
				self.in_wait_voices = []

	def set_presence(self, presence,type=0,url=None):
		self.presence["d"]["game"] = {
			"name":presence,
			"type":type,
			#"url":url
		}
		if self.gateway:
			asyncio.run_coroutine_threadsafe(self.gateway.send(self.presence),self.gateway.loop)

	def set_status(self, status):
		self.presence["d"]["status"]=status
		if self.gateway:
			asyncio.run_coroutine_threadsafe(self.gateway.send(self.presence),self.gateway.loop)

	def run(self):
		self.loop = asyncio.new_event_loop()
		print("Starting Bot")
		try:
			self.loop.run_until_complete(self.begin())
		except RuntimeError:
			print("Stopping Bot")

	def stop(self):
		self.gateway.stop()