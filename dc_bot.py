import os
import discord
from discord.ext import commands, tasks
#  from dotenv import load_dotenv
import json
from math import ceil

import subprocess
import time
import re

DIR = os.path.dirname(os.path.realpath(__file__))


SERVERS = {
    "Hania_I_pinkie": "/home/loleczkowo/mcdc/servers/Hania_I_pinkie",
}

UPDATE_CHAN_FILE = os.path.join(DIR, "update_chan.json")


def update_chan_file(new_chan_file):
    with open(UPDATE_CHAN_FILE, "w") as file:
        json.dump(new_chan_file, file, indent=4)


with open(UPDATE_CHAN_FILE, "r") as file:
    guild_update_chan = {int(k): v for k, v in json.load(file).items()}

#  load_dotenv()  # if you have an env file
bot = commands.Bot(command_prefix="mc ", intents=discord.Intents.all())
token = os.getenv("DISCORD_MC_SERVERS_TOKEN")

to_run = {}
#  {runname: {"time": time, "func": func}}

to_run_close = "close {server}"


@bot.event
async def on_ready():
    if not update.is_running():
        update.start()
    if not run_torun.is_running():
        run_torun.start()


def is_server_running(server_name):
    # Check if the screen session exists
    result = subprocess.run(
        f"screen -ls | grep -E '\\.{server_name}[[:space:]]'",
        shell=True, capture_output=True, text=True
    )

    return bool(result.stdout.strip())


def player_number(server_name):
    try:
        subprocess.run(
            f"screen -S {server_name} -X stuff 'list\n'",
            shell=True
            )
        time.sleep(1)
        subprocess.run(
            f"screen -S {server_name} -X hardcopy -h /tmp/mc_output.txt",
            shell=True
            )

        with open("/tmp/mc_output.txt", "r") as file:
            lines = file.readlines()

        print(lines)
        matches = re.findall(
            r"There are (\d+) of a max of \d+ players online:", lines)
        print(matches)
        return int(matches[-1]) if matches else 0
    except Exception as e:
        print(f"Error retrieving player count for {server_name}: {e}")
        return 0


def get_port(server):
    server_properties = f"{SERVERS[server]}/server.properties"
    with open(server_properties, "r") as file:
        for line in file:
            if line.startswith("server-port="):
                current_port = line.strip().split("=")[1]
                return current_port
    return -1


@tasks.loop(seconds=30)
async def run_torun():
    global to_run
    if not to_run:
        return
    new_to_run = {}
    for name, data in to_run.items():
        if data["time"] < time.time():
            data["func"]()
        else:
            new_to_run[name] = data
    to_run = new_to_run


@tasks.loop(seconds=30)
async def update():
    global guild_update_chan
    global to_run
    guild_update_chan_keys = guild_update_chan.keys()

    embed = discord.Embed(
        title="Servers Status",
        color=discord.Color.green()
    )

    for server in SERVERS.keys():
        if is_server_running(server):
            num = player_number(server)
            del_format = to_run_close.format(server=server)
            if num == 0:
                if del_format not in to_run:
                    to_run[del_format] = {
                        "time": time.time() + 60 * 5,
                        "func": lambda: stop_server_def(server)
                    }
                min = ceil((to_run[del_format]["time"]-time.time())/60)
                formated_time = f"`{min}`~ MINUTE"+"S"*(min != 1)
                status = f"🟡 **CLOSING IN {formated_time}** (`0 players`)"
            else:
                status = f"🟢 **RUNNING** (`{num} players`)"
                if del_format in to_run:
                    del to_run[del_format]
        else:
            status = "🔴 OFF"
        port = get_port(server)
        embed.add_field(
            name=f"**{server}** `everythingthatcounts.ddns.net:{port}`",
            value=status,
            inline=True
            )

    new_guild_update_chan = {}
    for guild in bot.guilds:
        if guild.id in guild_update_chan_keys:
            channel = guild.get_channel(guild_update_chan[guild.id]["chan"])
            if channel:
                try:
                    message = await channel.fetch_message(
                        guild_update_chan[guild.id]["id"])
                except discord.NotFound:
                    continue
                await message.edit(embed=embed)
                new_guild_update_chan[guild.id] = guild_update_chan[guild.id]
    if new_guild_update_chan != guild_update_chan:
        update_chan_file(new_guild_update_chan)
        guild_update_chan = new_guild_update_chan


@bot.command(name="set_update_channel")
@commands.has_permissions(administrator=True)
async def set_update_channel(ctx: commands.Context, channel_id):
    global guild_update_chan
    if channel_id.startswith("<#"):
        channel_id = channel_id[2:]
    if channel_id.endswith(">"):
        channel_id = channel_id[:-1]
    if not channel_id.isdigit():
        await ctx.send(f"`{channel_id}` is not a valid channel id")
        return

    channel = ctx.guild.get_channel(int(channel_id))
    if not channel:
        await ctx.send(f"Wrong channel id, `{channel_id}` does not exists")
        return
    embed = discord.Embed(
        title="Servers Status (loading)",
        color=discord.Color.red()
    )
    send_message = await channel.send(embed=embed)
    if not send_message:
        await ctx.send(f"Bot cannot send a message on `{channel_id}`")
        return

    if ctx.guild.id in guild_update_chan:
        oldchan = ctx.guild.get_channel(
            guild_update_chan[ctx.guild.id]["chan"])
        if oldchan:
            try:
                old_message = await oldchan.fetch_message(
                    guild_update_chan[ctx.guild.id]["id"])
                if old_message:
                    await old_message.delete()
                    await ctx.send("Deleted the old message")
            except discord.NotFound:
                pass

    guild_update_chan[int(ctx.guild.id)] = {
        "chan": int(channel_id),
        "id": int(send_message.id)
        }
    update_chan_file(guild_update_chan)
    await ctx.send(f"New channel for updates <#{channel_id}>")


@bot.command(name="port")
async def update_port(ctx, server, new_port):
    if server not in SERVERS:
        await ctx.send(f"Server `{server}` not found")

    if not new_port.isdigit():
        await ctx.send(f"The new port needs to be digits not `{new_port}`")
    new_port = int(new_port)

    server_properties = f"{SERVERS[server]}/server.properties"

    with open(server_properties, "r") as file:
        lines = file.readlines()

    with open(server_properties, "w") as file:
        for line in lines:
            if line.startswith("server-port="):
                file.write(f"server-port={new_port}\n")
            else:
                file.write(line)
    await ctx.send(f"Server `{server}` is now on port `{new_port}` set")

    if is_server_running(server):
        await ctx.send(f"Server `{server}` Is still on, reseting")
        stop_server_def(server, True)
        time.sleep(1)
        await start_server(ctx, server)


@bot.command(name="start")
async def start_server(ctx: commands.Context, name):
    if name in SERVERS:
        if is_server_running(name):
            await ctx.send(f"Server `{name}` is already running")
            return

        server_path = SERVERS[name]
        command = (f"screen -dmS {name} bash -c 'cd {server_path} && "
                   f"java -Xmx2G -Xms2G -jar minecraft_server.jar --nogui'")
        subprocess.Popen(command, shell=True, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
        await ctx.send(f"Server `{name}` started")
    else:
        await ctx.send(f"Server `{name}` not found")


@bot.command(name="stop")
async def stop_server(ctx: commands.Context, name):
    if name in SERVERS:
        if not is_server_running(name):
            await ctx.send(f"Server `{name}` is already stopped")
            return

        command = f"screen -S {name} -X stuff 'stop\n'"
        subprocess.run(command, shell=True)
        await ctx.send(f"Stopping server `{name}`...")

        timeout = 30
        elapsed = 0
        while is_server_running(name):
            time.sleep(1)
            elapsed += 1
            if elapsed >= timeout:
                print((f"Warning: Server `{name}` did not shut down"
                       f"within {timeout} seconds"))

        subprocess.run(f"screen -S {name} -X quit", shell=True)

        await ctx.send(f"Server `{name}` stopped")
    else:
        await ctx.send(f"Server `{name}` not found")


def stop_server_def(name, wait=False):
    if not is_server_running(name):
        return
    command = f"screen -S {name} -X stuff 'stop\n'"
    subprocess.run(command, shell=True)

    if wait:
        timeout = 30
        elapsed = 0
        while is_server_running(name):
            time.sleep(1)
            elapsed += 1
            if elapsed >= timeout:
                print((f"Warning: Server `{name}` did not shut down"
                       f"within {timeout} seconds"))
    subprocess.run(f"screen -S {name} -X quit", shell=True)


bot.run(token)
