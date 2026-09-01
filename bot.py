import discord
from discord.ext import commands
from discord.ui import View, Select, Button
import json
import os
from datetime import datetime
import asyncio
import re

# ==================== LOAD CONFIG ====================
with open("config.json", "r") as f:
    config = json.load(f)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="+", intents=intents)


def save_config():
    with open("config.json", "w") as f:
        json.dump(config, f, indent=4)


def get_staff_mentions():
    # Only this role gets pinged when a ticket is opened
    return "<@&1543437715679477890>"


def has_staff_permission(member: discord.Member):
    try:
        return any(str(role.id) in config["staffRoles"] for role in member.roles)
    except:
        return False


def clean_channel_name(name: str) -> str:
    # Make a valid Discord channel name from username
    name = name.lower()
    name = re.sub(r'[^a-z0-9\-]', '-', name)  # only allow a-z, 0-9, -
    name = re.sub(r'-+', '-', name).strip('-')
    return name[:90] if name else "ticket"


# ==================== TICKET SELECT MENU ====================
class TicketSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Make a ticket if need to contact a staff.",
                description="This option is for contacting a staff member.",
                value="support",
                emoji="🎫"
            ),
            discord.SelectOption(
                label="Scammer reports & files",
                description="This option is to report scammers.",
                value="scammer",
                emoji="🔗"
            ),
            discord.SelectOption(
                label="Claim your Reward!",
                description="This option is only available if you have won a giveaway.",
                value="reward",
                emoji="🎁"
            )
        ]
        super().__init__(
            placeholder="Make a selection",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_select"
        )

    async def callback(self, interaction: discord.Interaction):
        await create_ticket(interaction, self.values[0])


class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())


# ==================== TICKET BUTTONS ====================
class TicketButtons(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.primary, emoji="👤", custom_id="ticket_claim")
    async def claim_button(self, interaction: discord.Interaction, button: Button):
        if not has_staff_permission(interaction.user):
            return await interaction.response.send_message("Only staff can claim tickets.", ephemeral=True)

        embed = interaction.message.embeds[0]
        for field in embed.fields:
            if field.name.lower() == "claimed by":
                return await interaction.response.send_message("This ticket is already claimed.", ephemeral=True)

        embed.add_field(name="Claimed by", value=interaction.user.mention, inline=True)
        await interaction.message.edit(embed=embed)
        await interaction.response.send_message(f"Ticket claimed by {interaction.user.mention}")

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="ticket_close")
    async def close_button(self, interaction: discord.Interaction, button: Button):
        if not has_staff_permission(interaction.user):
            return await interaction.response.send_message("Only staff can close tickets.", ephemeral=True)

        await interaction.response.send_message("Closing ticket...")
        await close_ticket(interaction.channel, interaction.user)


# ==================== CREATE TICKET ====================
async def create_ticket(interaction: discord.Interaction, ticket_type: str):
    guild = interaction.guild
    member = interaction.user

    # Prevent multiple open tickets
    for channel in guild.text_channels:
        if channel.topic == f"ticket-{member.id}":
            return await interaction.response.send_message(
                f"You already have an open ticket: {channel.mention}", ephemeral=True
            )

    config["ticketCounter"] += 1
    save_config()

    # Channel name = username
    channel_name = clean_channel_name(member.name)

    # Different category for each ticket type
    if ticket_type == "support":
        category_id = 1542842587113586698
    elif ticket_type == "scammer":
        category_id = 1542842435325927434
    else:  # reward
        category_id = 1542842640851148851

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        member: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            attach_files=True,
            read_message_history=True
        ),
        guild.me: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            manage_channels=True,
            manage_messages=True
        )
    }

    for role_id in config["staffRoles"]:
        role = guild.get_role(int(role_id))
        if role:
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                attach_files=True,
                read_message_history=True,
                manage_messages=True
            )

    category = guild.get_channel(category_id)

    channel = await guild.create_text_channel(
        name=channel_name,
        category=category,
        topic=f"ticket-{member.id}",
        overwrites=overwrites
    )

    if ticket_type == "support":
        embed = discord.Embed(
            title=f"Ticket opened by {member.name}",
            description="Thank you for contacting the support\nPlease describe your problem and wait for an answer",
            color=0xED4245,
            timestamp=datetime.utcnow()
        )
    elif ticket_type == "scammer":
        embed = discord.Embed(
            title=f"Ticket opened by {member.name}",
            description=(
                "**SCAMMER REPORT SERVICE**\n\n"
                "Please follow the format:\n\n"
                "`DISCORDIDOFSCAMMER - ID`\n"
                "`DISCORDIDOFVICTIM - ID`\n"
                "`ROBLOXUSEROFSCAMMER - USER`\n"
                "`ROBLOXUSEROFVICTIME - USER`\n\n"
                "**Deal:** (ex: Robux for Brainrots)\n"
                "**Evidences:**\n"
                "(Screens / Records only (Must include: The user of the scammer in the conversation, when he blocks or him assuming the scam))"
            ),
            color=0xED4245,
            timestamp=datetime.utcnow()
        )
    else:  # reward
        embed = discord.Embed(
            title=f"Ticket opened by {member.name}",
            description=(
                "**REWARD CLAIMING SERVICE**\n\n"
                "Please follow the format:\n\n"
                "`DISCORDIDOFWINNER - ID`\n"
                "`ROBLOXUSEROFWINNER - USER`\n\n"
                "**Prize:** (EXAMPLE: x1 secret)\n"
                "**Evidences:**\n"
                "(Screens of the giveaway winning / etc)"
            ),
            color=0xED4245,
            timestamp=datetime.utcnow()
        )

    # Shows username clearly
    await channel.send(
        content=(
            f"{get_staff_mentions()}\n"
            f"**Opened by:** {member.mention}\n"
            f"**Username:** `{member.name}`\n"
            f"**Display Name:** `{member.display_name}`"
        ),
        embed=embed,
        view=TicketButtons()
    )

    await interaction.response.send_message(f"Ticket created: {channel.mention}", ephemeral=True)


# ==================== CLOSE TICKET ====================
async def close_ticket(channel: discord.TextChannel, closer: discord.Member):
    messages = [msg async for msg in channel.history(limit=100, oldest_first=True)]

    transcript = "---- TICKET LOGS ----\n\n"
    for msg in messages:
        time = msg.created_at.strftime("%d/%m/%Y %H:%M")
        transcript += f"{time} - {msg.author}: {msg.content}\n"
        if msg.embeds:
            transcript += f"<EMBED {msg.embeds[0].title or 'Embed'}>\n"

    with open("log.txt", "w", encoding="utf-8") as f:
        f.write(transcript)

    file = discord.File("log.txt", filename="log.txt")

    log_channel = bot.get_channel(int(config["transcriptChannelId"]))
    if log_channel:
        await log_channel.send(
            content=f"Ticket closed by {closer.mention}\nChannel: `{channel.name}`",
            file=file
        )

    if channel.topic and channel.topic.startswith("ticket-"):
        try:
            user_id = int(channel.topic.replace("ticket-", ""))
            user = await bot.fetch_user(user_id)
            await user.send(
                content="Your ticket was closed\nHere is a transcript of the ticket",
                file=discord.File("log.txt", filename="log.txt")
            )
        except:
            pass

    # Delete instantly (0 seconds)
    await channel.delete()

    if os.path.exists("log.txt"):
        os.remove("log.txt")


# ==================== EVENTS ====================
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("Bot is ready!")

    bot.add_view(TicketView())
    bot.add_view(TicketButtons())


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # Bot mention shows prefix
    if bot.user.mentioned_in(message) and not message.mention_everyone:
        content = message.content.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "").strip()
        if len(content) < 3:
            await message.reply("My prefix on this server is: **+**", mention_author=False)
            return

    await bot.process_commands(message)


# ==================== COMMANDS ====================
@bot.command(name="panel")
@commands.has_permissions(administrator=True)
async def panel_command(ctx: commands.Context):
    """Sends the ticket panel"""
    embed = discord.Embed(
        title="Tickets",
        description="You can use this menu to create a ticket and contact the staff",
        color=0xED4245
    )
    await ctx.send(embed=embed, view=TicketView())
    try:
        await ctx.message.delete()
    except:
        pass


@bot.command(name="commands")
async def commands_command(ctx: commands.Context):
    if not has_staff_permission(ctx.author):
        return await ctx.reply("❌ You do not have permission to use this command.", mention_author=False)

    embed = discord.Embed(
        title="Ticket Bot Commands",
        description="Here are all the available commands:",
        color=0xED4245,
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="`+panel`", value="Sends the ticket panel in the current channel\n*(Admin only)*", inline=False)
    embed.add_field(name="`+commands`", value="Shows this help menu", inline=False)
    embed.add_field(name="`+rename <name>`", value="Renames the current ticket\nExample: `+rename giveaway won`", inline=False)
    embed.add_field(name="`+claim`", value="Claims the current ticket", inline=False)
    embed.add_field(name="`+close`", value="Closes the current ticket and sends a transcript", inline=False)
    embed.add_field(name="`+testperm`", value="Checks if the bot sees you as staff", inline=False)
    embed.set_footer(text="Prefix: + | Staff only")

    await ctx.reply(embed=embed, mention_author=False)


@bot.command(name="testperm")
async def testperm_command(ctx: commands.Context):
    """Check if the bot recognizes you as staff"""
    if has_staff_permission(ctx.author):
        roles = [role.name for role in ctx.author.roles if str(role.id) in config["staffRoles"]]
        await ctx.reply(
            f"✅ You **have** staff permission.\n"
            f"Matching roles: {', '.join(roles) if roles else 'None found (but check passed)'}",
            mention_author=False
        )
    else:
        await ctx.reply(
            "❌ You do **not** have staff permission.\n"
            "Make sure one of your roles is in the `staffRoles` list in config.json.",
            mention_author=False
        )


@bot.command(name="rename")
async def rename_command(ctx: commands.Context, *, new_name: str = None):
    if not has_staff_permission(ctx.author):
        return await ctx.reply("❌ You do not have permission to use this command.", mention_author=False)

    if not ctx.channel.topic or not str(ctx.channel.topic).startswith("ticket-"):
        return await ctx.reply("❌ This command can only be used inside ticket channels.")

    if not new_name or len(new_name.strip()) < 2:
        return await ctx.reply("❌ Please provide a name.\nExample: `+rename giveaway won`")

    clean_name = new_name.lower().replace(" ", "-")[:100]

    try:
        await ctx.channel.edit(name=clean_name)
        await ctx.reply("✅ Ticket renamed successfully")
    except discord.Forbidden:
        await ctx.reply("❌ I don't have **Manage Channels** permission.")
    except Exception as e:
        await ctx.reply(f"❌ Error: `{e}`")


@bot.command(name="claim")
async def claim_command(ctx: commands.Context):
    if not has_staff_permission(ctx.author):
        return await ctx.reply("❌ You do not have permission to use this command.", mention_author=False)

    if not ctx.channel.topic or not str(ctx.channel.topic).startswith("ticket-"):
        return await ctx.reply("❌ This command can only be used inside ticket channels.")

    try:
        found = False
        async for msg in ctx.channel.history(limit=30):
            if msg.author.id == bot.user.id and msg.embeds:
                embed = msg.embeds[0]

                for field in embed.fields:
                    if field.name.lower() == "claimed by":
                        return await ctx.reply("❌ This ticket is already claimed.")

                embed.add_field(name="Claimed by", value=ctx.author.mention, inline=True)
                await msg.edit(embed=embed)
                found = True
                break

        if found:
            await ctx.reply(f"✅ Ticket claimed by {ctx.author.mention}")
        else:
            await ctx.reply("❌ Could not find the ticket message.")
    except Exception as e:
        await ctx.reply(f"❌ Error while claiming: `{e}`")


@bot.command(name="close")
async def close_command(ctx: commands.Context):
    if not has_staff_permission(ctx.author):
        return await ctx.reply("❌ You do not have permission to use this command.", mention_author=False)

    if not ctx.channel.topic or not str(ctx.channel.topic).startswith("ticket-"):
        return await ctx.reply("❌ This command can only be used inside ticket channels.")

    await ctx.reply("Closing ticket...")
    await close_ticket(ctx.channel, ctx.author)


# ==================== RUN ====================
# Reads token from Railway Environment Variable first, then falls back to config.json
bot.run(os.getenv("TOKEN") or config.get("token"))
