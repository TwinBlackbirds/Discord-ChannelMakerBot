# author: Michael Amyotte (twinblackbirds)
# date: 8/23/24
# definition of skeleton bot client 

# internal (python built-ins)
import os
import shutil
import urllib.request as requests
import xml.etree.ElementTree as et
from sys import platform
from datetime import datetime
# self-made
import models.Channel as channelModel
import models.Role as roleModel

# 3rd pty (pip install -r requirements.txt)
import discord
import dotenv

## constant variables

# represents command prefix

ENV = dotenv.find_dotenv()
dotenv.load_dotenv(ENV)

PREFIX = os.environ["PREFIX"]

class Skeleton(discord.Client):
	# for confirming deletion of a skeleton, needs to be class-wide so it can encompass the scope of all methods
	Confirm_Flag = False
	Confirm_FilePath = ""
	# for accessing current channel, guild, user, etc. class-wide so it doesn't have to be passed around
	# represents the most recent message the bot has received
	Working_Message = object
	### preps the bot to run
	def prepare(self):
		# clear attachments folder 
		if os.path.exists("attachments"):
			shutil.rmtree("attachments")
		os.mkdir("attachments")

		# create "skeletons" folder if it doesn't exist already
		# will be used to save skeletons for reuse after user uploads it the first time
		if not os.path.exists("skeletons"):
			os.mkdir("skeletons")
		return
		
	def log(self, content):
		if not os.path.exists("log.txt"):
			open("log.txt", "w+").close()
		with open("log.txt", "a+") as f:
			f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {content}\n")
		return

	### internal
	async def quick_update_status(self):
		game = discord.Activity(name="Bot Online", state=f"[Ready] Prefix: {PREFIX}", type=discord.ActivityType.custom)
		await self.change_presence(status=discord.Status.online, activity=game)
		return

	### runs on bot startup
	async def on_ready(self):
		self.prepare()
		await self.quick_update_status()
		self.log(f'bot {self.user} is online using prefix: {PREFIX}')
		return

	### on_message event, heart of the bot's reactivity
	async def on_message(self, message):
		# if user is not administrator, decline their command
		admin_status = message.channel.permissions_for(message.author).administrator
		if not admin_status and message.content.startswith(PREFIX):
			await message.channel.send("you need to be an administrator in order to use this bot")
			return
		self.Working_Message = message
		lower = self.Working_Message.content.lower()
		if lower == f'{PREFIX}uploadskeleton':
			await self.upload_skeleton()
		elif lower.startswith(f'{PREFIX}changeprefix'):
			await self.change_prefix()
		elif lower == f"{PREFIX}help":
			await self.print_help()
		elif lower == f"{PREFIX}skeletons":
			await self.display_saved_skeletons()
		elif lower.startswith(f"{PREFIX}executeskeleton"):
			await self.execute_skeleton()
		elif lower.startswith(f"{PREFIX}deleteskeleton"):
			await self.delete_skeleton()
		elif lower.startswith(f"{PREFIX}downloadskeleton"):
			await self.download_skeleton()
		# -- debug commands below this line -- 
		elif lower == f"{PREFIX*3}wipe":
			await self.wipe_server()
		

	### internal, for 'help' command
	def get_commands_list(self):
		cmds = [
			{
				'name': f'{PREFIX}help',
				'description': 'Prints this dialogue'
			},
			{
				'name': f'{PREFIX}changePrefix <prefix>',
				'description': f'Change the prefix used for commands (default: **!**)'
			},
			{
				'name': f'{PREFIX}uploadSkeleton <<.xml attachment>>', 
				'description': 'Upload a .xml file in order to be used for ' +
												'server skeletoning (takes 1 or more attachments)'
			}, 
			{
				'name': f'{PREFIX}downloadSkeleton <skeleton reference>',
				'description': 'Provides a skeleton file as an attachment to download'
			},
			{
				'name': f'{PREFIX}skeletons',
				'description': 'Display all currently saved skeletons (takes 0 arguments)'
			},
			{
				'name': f'{PREFIX}executeSkeleton <skeleton reference>',
				'description': f'Execute a skeleton on the current guild. View available skeletons & their references with *{PREFIX}skeletons*'
			}, 
			{
				'name': f'{PREFIX}deleteSkeleton <skeleton reference>',
				'description': f'Delete a currently saved skeleton. View available skeletons & their references with *{PREFIX}skeletons*'
			}
			# wipe command is purposefully omitted
		]
		return cmds

	### user command
	async def download_skeleton(self):
		msg_space_sep = self.Working_Message.content.split(" ")
		# skeleton ref is taken as 2nd word provided
		filepath = "./skeletons/" + msg_space_sep[1] + ".xml" if len(msg_space_sep) > 1 else None
		# validate skeleton_ref exists and is provided
		if filepath == None:
			await self.Working_Message.channel.send("please provide a skeleton reference along with your message!")
			return
		if not os.path.exists(filepath):
			await self.Working_Message.channel.send(f"invalid skeleton reference <{msg_space_sep[1]}>! (hint: view {PREFIX}skeletons)")
			return
		# attach skeleton
		file = discord.File(filepath)
		await self.Working_Message.channel.send(content="here is the skeleton file you requested:", file=file)
		return

	### user command
	async def change_prefix(self):
		# take global context for PREFIX, ENV variables
		global PREFIX, ENV
		# seperate message by spaces
		msg_space_sep = self.Working_Message.content.split(" ")
		# prefix is taken as 2nd word provided
		temp_prefix = msg_space_sep[1] if len(msg_space_sep) > 1 else None 
		if PREFIX == temp_prefix:
			await self.Working_Message.channel.send("that's already the prefix!")
			return
		# validate prefix is the right length and a special character
		if len(temp_prefix) != 1 or temp_prefix.isalnum():
			await self.Working_Message.channel.send("invalid prefix! choose a single special character")
			return
		# update .env file for future sessions
		dotenv.set_key(ENV, "PREFIX", temp_prefix)
		# set prefix variable for remainder of current session
		PREFIX = temp_prefix
		await self.quick_update_status()
		self.log(f"now using prefix: {PREFIX}")
		await self.Working_Message.channel.send(f"changed prefix to: {PREFIX}")

	### internal, returns (return code, skeleton reference | None)
	async def save_skeleton_attachment(self, attachment):
		temp_path = "./attachments/" + attachment.filename
		payload = (0, None)
		# if not an .xml, don't even bother downloading it
		if not attachment.filename.endswith(".xml"):
			payload = (1, None)
			return payload
		# if filepath is the same as an example, don't bother downloading it either
		elif attachment.filename == "exampleRole.xml" or attachment.filename == "exampleChannel.xml":
			payload = (3, None)
			return payload
		# downloads attm to 'attachments' folder where it will be temporarily held until it's validated
		await attachment.save(fp=temp_path)
		# we don't need the elements of the xml here (if it is valid) so we can ignore the third return value in the tuple
		(xml_is_valid, skeleton_type, _elements) = await self.validate_and_read_xml(temp_path)
		# if xml is not in correct format, discard it
		if not xml_is_valid:
			payload = (2, None)
		# otherwise, save it to 'skeletons/{type}' folder
		else:
			# create 'permanent' location for xml file
			new_path = f'./skeletons/{skeleton_type}/' + attachment.filename
			if not os.path.exists(new_path):
				os.mkdir(new_path)
			# move the file from the temp location to the 'permanent' one
			shutil.move(temp_path, new_path)
			payload = (0, f"{skeleton_type}/{attachment.filename.replace('.xml', '')}")

		# clear attachments folder at the end
		shutil.rmtree("./attachments")
		os.mkdir("./attachments")

		return payload

	### user command
	async def upload_skeleton(self):
		self.log("receiving skeleton upload")
		attms = self.Working_Message.attachments
		num_attms = len(attms)
		self.log(f"received {num_attms} items")
		if num_attms == 0:
			await self.Working_Message.channel.send("please attach a .xml skeleton to your message before sending!")

		for attm in attms:
			(return_code, ret_value) = await self.save_skeleton_attachment(attm)
			if return_code == 0 and ret_value is not None:
				# successful execution
				# here, ret_value is a string representing user reference to saved skeleton
				await self.Working_Message.channel.send(f"skeleton saved. skeleton reference: **{ret_value}**")
			elif return_code == 1:
				# if file is not .xml
				# here, ret_value is None
				await self.Working_Message.channel.send(f"problematic attachment: <{attm.filename}>, invalid file type")
			elif return_code == 2:
				# if file is invalid xml
				# here, ret_value is None
				await self.Working_Message.channel.send(f"problematic attachment: <{attm.filename}>, improper xml format or xml is ill-formed (refer to sample skeleton)")
			elif return_code == 3:
				# if user tries to overwrite examples
				# here, ret_value is None
				await self.Working_Message.channel.send(f"cannot overwrite example skeletons! choose a new file name and try again")
		return

	### internal function, returns (bool, T, list<T>)
	### represents (validity, type, retrieved elements (if any))
	async def validate_and_read_xml(self, filename):
		string = ""
		with open(filename) as f:
			string = f.read()

		# handle ill-formed xml
		try:
			root = et.fromstring(string)
		except:
			return (False, "", [])

		skeleton_type = root.find('Type')
		# check there is a Type property at all
		if skeleton_type != None:
			skeleton_type = skeleton_type.text.strip().lower()
		else: 
			return (False, "", [])
		# match type of skeleton
		if skeleton_type == 'channel':
			channels = await self.parse_channel_skeleton(root)
			for channel in channels:
				permissions = await self.parse_overwrite_skeleton(channel.perm_overwrites)
				# for when 
				if permissions == {None}:
					return (False, "", [])
			if len(channels) > 0:
					return (True, 'Channel', channels)
			else:
				return (False, "", [])
		elif skeleton_type == 'role':
			roles = self.parse_role_skeleton(root)
			if len(roles) > 0:
					return (True, 'Role', roles)
			else:
				return (False, "", [])
		return (False, "", [])

	async def display_saved_skeletons(self):
		msg = "Available skeletons:\n\n"
		msg += "**Role**\n"
		role_skeletons = os.listdir("skeletons/Role")
		for skeleton in role_skeletons:
			msg += f"{skeleton.replace('.xml', '')}\n"
		msg += "\n**Channel**\n"
		channel_skeletons = os.listdir("skeletons/Channel")
		for skeleton in channel_skeletons:
			msg += f"{skeleton.replace('.xml', '')}\n"
		msg += "\nNote: skeletons are referred to like such: *<Type>/<Filename>* (e.g. Role/exampleRole)"
		await self.Working_Message.channel.send(msg)
		return

	### internal function 
	def reset_confirmation(self, flag=False, fp=""):
		self.Confirm_Flag = flag
		self.Confirm_FilePath = fp

	### user command
	async def delete_skeleton(self):
		msg_space_sep = self.Working_Message.content.split(" ")
		if len(msg_space_sep) != 2:
			await self.Working_Message.channel.send(f"please provide a single skeleton reference to delete (hint: view {PREFIX}skeletons)")
			self.reset_confirmation()
			return
		# prefix is taken as 2nd word provided
		filepath = "./skeletons/" + msg_space_sep[1] + ".xml" if len(msg_space_sep) > 1 else None
		# validate prefix is the right length and a special character
		if filepath == None:
			await self.Working_Message.channel.send("please provide a skeleton reference along with your message!")
			self.reset_confirmation()
			return
		if not os.path.exists(filepath):
			await self.Working_Message.channel.send(f"invalid skeleton reference <{msg_space_sep[1]}>! (hint: view {PREFIX}skeletons)")
			self.reset_confirmation()
			return

		# ensure user is not trying to delete sample skeleton
		if filepath.lower() == "./skeletons/role/sampleroleccaffold.xml" \
		or filepath.lower() == "./skeletons/channel/samplechannelskeleton.xml" \
		or filepath.lower() == "./skeletons/sampleinvalidskeleton.xml":
			await self.Working_Message.channel.send("cannot delete sample skeletons!")
			self.reset_confirmation()
			return

		# confirmation that user wants to delete for sure
		if self.Confirm_Flag == False or filepath != self.Confirm_FilePath:
			await self.Working_Message.channel.send("are you sure you want to delete skeleton? enter the previous command again to confirm")
			self.reset_confirmation(flag=True, fp=filepath)
		else:
			# if user has passed confirmation stage and would like to delete 
			try:
				os.remove(filepath)
				await self.Working_Message.channel.send("skeleton successfully deleted")
				
			except:
				await self.Working_Message.channel.send("error occured deleting file. delete it manually or check filepath and try again")
			# reset confirmation flags to default	
			self.reset_confirmation()

		return

	### user command, runs a saved skeleton on the current guild
	async def execute_skeleton(self):
		guild = self.Working_Message.guild   
		msg_space_sep = self.Working_Message.content.split(" ")
		# skeleton ref is taken as 2nd word provided
		filepath = "./skeletons/" + msg_space_sep[1] + ".xml" if len(msg_space_sep) > 1 else None
		# validate skeleton_ref exists and is provided
		if filepath == None:
			await self.Working_Message.channel.send("please provide a skeleton reference with your message!")
			return
		if len(msg_space_sep) != 2 or not os.path.exists(filepath):
			await self.Working_Message.channel.send(f"invalid skeleton reference <{msg_space_sep[1]}>! (hint: view {PREFIX}skeletons)")
			return

		# we don't need the validity here, just the type and elements
		(_valid, T, elements) = await self.validate_and_read_xml(filepath)
		if T == 'Channel':
			for element in elements:
				if element.channel_type.lower() == 'text':
					await guild.create_text_channel(
						element.channel_name,
						category=self.find_category(self.Working_Message, element.category),
						topic=element.channel_topic,
						nsfw=element.is_nsfw,
						slowmode_delay=element.rate_limit_per_user,
						overwrites=await self.parse_overwrite_skeleton(self.Working_Message, element.perm_overwrites)
					)
				elif element.channel_type.lower() == 'voice':
					await guild.create_voice_channel(
						element.channel_name,
						category=self.find_category(self.Working_Message, element.category),
						bitrate=element.bitrate,
						user_limit=element.user_limit,
						overwrites=await self.parse_overwrite_skeleton(self.Working_Message, element.perm_overwrites)
					)
				elif element.channel_type.lower() == 'category':
					await guild.create_category(
						element.channel_name,
						overwrites=await self.parse_overwrite_skeleton(self.Working_Message, element.perm_overwrites)
					)

			await self.Working_Message.channel.send(f"successfully executed skeleton {msg_space_sep[1]}")
			
		elif T == 'Role':
			for element in elements:
				colour = discord.Color.from_str(element.role_color)
				await guild.create_role(
					name=element.role_name,
					permissions=element.role_perms,
					color=colour,
					mentionable=element.role_mentionable,
					hoist=element.role_hoist
				)
			await self.Working_Message.channel.send(f"successfully executed skeleton {msg_space_sep[1]}")
		return
	
	### internal function used to find a category by name and return the Category object
	def find_category(self, cat_name):
		if cat_name == '0':
			return None
		cats = self.Working_Message.guild.categories
		for cat in cats:
			if cat.name.lower() == cat_name.lower():
				return cat
			
	### internal function used to find a role by name and return the Role object
	async def find_role(self, role_name):
		lower = role_name.lower()
		if lower == 'everyone':
			return self.Working_Message.guild.default_role
		roles = self.Working_Message.guild.roles
		for role in roles:
			if lower == role.name.lower(): 
				return role

	### internal, xml_element is the root (Skeleton) element of XML
	### returns a list of discord.Channel elements
	async def parse_channel_skeleton(self, xml_element):
		channels = xml_element.findall('Channels/Channel')
		channel_list = []
		for channel in channels:
			c = channelModel.Channel()
			# mandatory categories
			c.channel_name = channel.find('ChannelName').text.strip()
			c.channel_type = channel.find('ChannelType').text.strip()
			# get channel topic, category
			channelTopic = channel.find('ChannelTopic')
			c.channel_topic = channelTopic.text.strip() if channelTopic != None else ""
			category = channel.find('Category')
			if category == None:
				category = '0'
			else:
				category = category.text.strip()
			c.category = category
			# get NSFW status
			NSFW = channel.find('NSFW')
			if NSFW == None:
				NSFW = False
			else: 
				NSFW = True if NSFW.text.strip().lower() == 'true' else False
			c.is_nsfw = NSFW
			# get voice channel properties 
			bitRate = channel.find('Bitrate')
			c.bitrate = int(bitRate.text.strip()) if bitRate != None else 64000
			userLimit = channel.find("UserLimit")
			c.user_limit = int(userLimit.text.strip()) if userLimit != None else 0
			# get permissions
			permissions = channel.findall('PermissionOverwrites/Overwrite')
			c.perm_overwrites =  permissions if permissions != None else [] 
			syncPermissions = channel.find('SyncPermissions')
			if syncPermissions == None:
				syncPermissions = True
			else:
				syncPermissions = True if syncPermissions.text.strip().lower() == 'true' else False
			# get slowmode
			rateLimit = channel.find('RateLimitPerUser')
			c.rate_limit_per_user = int(rateLimit.text.strip()) if rateLimit != None else 0

			channel_list.append(c)

		return channel_list
	
	### debug command, delete every 'skeletonable' part of the server except a general text channel
	### DO NOT USE THIS COMMAND UNLESS YOU WANT TO WIPE THE ENTIRE SERVER
	async def wipe_server(self):
		await self.Working_Message.channel.send("running 'wipe' debug command (note: the bot can only delete roles if they are 'managable' by the bot)")
		guild = self.Working_Message.guild
		for channel in guild.channels:
			if channel.name.lower() != 'general':
				await channel.delete()
		for vc in guild.voice_channels:
			await vc.delete()
		for category in guild.categories:
			await category.delete()
		for role in guild.roles:
			if role.is_assignable():
				await role.delete()
		await self.Working_Message.channel.send("wiped all 'skeletonable' elements from the server")

	### internal, overwrites is xml object, returns {discord.Role: discord.PermissionOverwrite}
	async def parse_overwrite_skeleton(self, overwrites):
		overwrite_dict = {}
		for overwrite in overwrites:
			_id = overwrite.find('ID') 
			id = int(_id.text.strip()) if _id != None else 0
			key = object
			if overwrite.find("Type").text.lower().strip() == 'member':
				key = self.get_user(id)
			else:
				if id > 0:
					key = self.Working_Message.guild.get_role(id)
				else:
					name_to_search = overwrite.find("Name")
					if name_to_search == None:
						name_to_search = 'everyone'
					else:
						name_to_search = name_to_search.text.lower().strip()
					if name_to_search == 'everyone':
						key = self.Working_Message.guild.default_role
					else:
						key = await self.find_role(name_to_search)
			if key == None:
				await self.Working_Message.channel.send("invalid ID discovered in skeleton! could not continue. (are all roles created?)")
				return {None}
			allows = overwrite.find("Allow")
			allow = int(allows.text.strip()) if allows != None else 0
			denies = overwrite.find("Deny")
			deny = int(denies.text.strip()) if denies != None else 0
			allow_perms = discord.Permissions(allow)
			deny_perms = discord.Permissions(deny)
			overwrite_val = discord.PermissionOverwrite.from_pair(allow=allow_perms, deny=deny_perms)
			overwrite_dict[key] = overwrite_val
		return overwrite_dict

	### internal, permission is Element< 'Permissions' >
	def parse_permission_skeleton(self, permission):
		# take inner value from 'Allow', a bitwise value representing flags which in turn represent allowed permissions
		allow = permission.find("Allow")
		if allow == None:
			allow = 0
		else:
			allow = int(allow.text.strip())
		p = discord.Permissions()
		return p

	### internal, xml_element is the root (Skeleton) element of XML
	def parse_role_skeleton(self, xml_element):
		roles = xml_element.findall("Roles/Role")
		roles_list = []
		for role in roles:
			r = roleModel.Role()
			r.role_name = role.find('RoleName').text.strip()
			color = role.find('RoleColor')
			r.role_color = color.text.strip() if color != None else "#adadad"
			mentionable = role.find('Mentionable')
			if mentionable == None:
				mentionable = 'true'
			else:
				mentionable = mentionable.text.strip().lower()
			r.role_mentionable = True if mentionable == 'true' else False
			hoist = role.find('Hoist')
			if hoist == None:
				hoist = 'false'
			else:
				hoist = hoist.text.strip().lower()
			r.role_hoist = True if hoist == 'true' else False
			role_perms = role.find('Permissions')
			if role_perms == None:
				role_perms = discord.Permissions(0)
			else:
				role_perms = self.parse_permission_skeleton(role_perms)
			r.role_perms = role_perms
			roles_list.append(r)
		return roles_list
	
	### user command
	async def print_help(self):
		msg = "*Note: commands are not case-sensitive, however skeleton references are.*\n\n"
		for command in self.get_commands_list():
			msg += f"**{command['name']}**\n\t{command['description']}\n\n"
		await self.Working_Message.channel.send(msg)
