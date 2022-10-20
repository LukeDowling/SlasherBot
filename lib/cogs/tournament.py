import emoji
import random
import math
from discord import Embed
from discord import Member
from discord.ext.commands import Cog
from discord.ext.commands import command
from discord.ext.commands import has_permissions

from .. db import db

checkmark = "✅"


def user_authorized(ctx):
    return any(role.name == "Draft Admin" for role in ctx.author.roles) or ctx.author.id == 479887202156019712


def get_draft_id(ctx):
    draft_id = db.field("SELECT MessageID FROM draftMessage WHERE ChannelID = ?", ctx.channel.id)

    return draft_id


def draft_exists(ctx):
    draft_found = db.field("SELECT MessageID FROM draftMessage WHERE ChannelID = ?", ctx.channel.id)

    return draft_found is not None


def draft_description(current_captain):
    draft_description = f"Captains take turns choosing players remaining in the " \
                         "draft pool. Depending on the number of players and the " \
                         "selected team size some teams may have extra players as " \
                         "substitutes. \n\n" \
                        f"{current_captain}'s turn to choose using: >pick [@mention] \n"

    return draft_description


def players(ctx):
    players = []

    player_ids = db.records("SELECT PlayerID FROM draftPlayers")
    for player in player_ids:
        players.append(ctx.guild.get_member(player[0]))
    
    return players


def draft_pool(ctx):
    draft_pool = []
    
    player_ids = db.records("SELECT PlayerID FROM draftPlayers WHERE Team IS NULL")
    for player in player_ids:
        draft_pool.append(ctx.guild.get_member(player[0]))

    return draft_pool


def draft_pool_list(ctx):
    draft_pool_list = ""
    players = draft_pool(ctx)

    for player in players:
        draft_pool_list += player.display_name + " - "

    return draft_pool_list


def captains(ctx):
    captains = []
    captain_ids = db.records("SELECT PlayerID FROM draftPlayers WHERE Captain = 1")
    for captain in captain_ids:
        captains.append(ctx.guild.get_member(captain[0]))

    return captains


def captain_list(ctx):
    captain_list = ""
    captain_users = captains(ctx)

    for captain in captain_users:
        captain_list += captain.display_name + " - "

    return captain_list


def current_captain(ctx):
    captain_id = db.field("SELECT PlayerID FROM draftPlayers "
                          "WHERE DraftOrder = ?", len(draft_pool(ctx)) % len(captains(ctx)))

    captain = ctx.guild.get_member(captain_id)

    return captain


def team_size(ctx):
    team_size = db.field("SELECT TeamSize FROM draftMessage WHERE ChannelID = ?", ctx.channel.id)

    return team_size


def draft_embed(ctx):
    if team_size(ctx) != 1: 
        draft_embed = Embed(title="Draft Phase",
                      description=draft_description(current_captain(ctx).display_name),
                      colour=ctx.author.colour)
                    
        draft_embed.add_field(name="Captains:", value=captain_list(ctx), inline=False)
        draft_embed.add_field(name="Draft pool:", value=draft_pool_list(ctx), inline=False)

    else:
        draft_embed = Embed(title="Duel Tournament Mode",
                      colour=ctx.author.colour)
                    
        draft_embed.add_field(name="Duelists:", value=captain_list(ctx), inline=False)

    return draft_embed


def registration_exists(ctx):
    registration_found = team_size(ctx)
    return registration_found is not None


def get_team(ctx, player: Member):
    team = []

    team_id = db.field("SELECT Team FROM draftPlayers WHERE PlayerID = ?", player.id)
    player_ids = db.records("SELECT PlayerID FROM draftPlayers WHERE Team = ?", team_id)
    for player in player_ids:
        team.append(ctx.guild.get_member(player[0]))

    return team


def get_captain(ctx, player: Member):
    team_id = db.field("SELECT Team FROM draftPlayers WHERE PlayerID = ?", player.id)
    captain_id = db.field("SELECT PlayerID FROM draftPlayers WHERE PlayerID = ?", team_id)

    return ctx.guild.get_member(captain_id)


def team_list(ctx, player: Member):
    team_list = ""
    team_players = get_team(ctx, player)

    for player in team_players:
        team_list += player.display_name + "\n"

    return team_list
    

def round_count(ctx):
    team_count = len(captains(ctx))

    rounds = 1
    while 2**rounds < team_count:
        rounds += 1

    return rounds


def generate_bracket(ctx):
    draft_id = get_draft_id(ctx)
    rounds = round_count(ctx)
    round_number = 1
    
    while round_number <= rounds:
        match_number = 1
        while match_number <= 2**(rounds - round_number):
            db.execute("INSERT INTO tournament "
                       "(MessageID, RoundNumber, MatchNumber) "
                       "VALUES (?, ?, ?)", draft_id, round_number, match_number)
            
            match_number += 1

        round_number += 1

        
def bracket_exists(ctx):
    bracket = db.field("SELECT MessageID FROM tournament WHERE MessageID = ?", get_draft_id(ctx))

    return bracket is not None


def populate_bracket(ctx):
    team_count = len(captains(ctx))
    match_count = 2**(round_count(ctx) - 1)
    team_assignments = match_count * 2
    captains_list = captains(ctx)

    i = 0
    while i < team_assignments:
        match_number = ((i % match_count) + 1)
        captain_id = db.field("SELECT PlayerID FROM draftPlayers "
                              "WHERE DraftOrder = ?", i)

        red_populated = db.field("SELECT RedTeam FROM tournament "
                                 "WHERE RoundNumber = 1 "
                                 "AND MatchNumber = ?", match_number)

        if red_populated is None:
            db.execute("UPDATE tournament "
                      f"SET RedTeam = {captain_id} "
                       "WHERE RoundNumber = 1 "
                      f"AND MatchNumber = {match_number}")

        elif i < team_count:
            db.execute("UPDATE tournament "
                      f"SET BlueTeam = {captain_id} "
                       "WHERE RoundNumber = 1 "
                      f"AND MatchNumber = {match_number}")

        else:
            db.execute("UPDATE tournament "
                      f"SET BlueTeam = 'bye' "
                       "WHERE RoundNumber = 1 "
                      f"AND MatchNumber = {match_number}")

            next_match = math.ceil(match_number / 2)

            if match_number % 2 == 0:
                next_team = "BlueTeam"

            else:
                next_team = "RedTeam"

            db.execute("UPDATE tournament "
                      f"SET {next_team} = {red_populated} "
                      f"WHERE RoundNumber = {2} "
                      f"AND MatchNumber = {next_match}")

        i += 1


def get_current_match(ctx):
    draft_id = get_draft_id(ctx)
    rounds = round_count(ctx)

    round_number = 1
    while round_number <= rounds:
        match_number = 1
        while match_number <= 2**(rounds - round_number):
            current_match = db.record("SELECT RoundNumber, MatchNumber, "
                                      "RedTeam, BlueTeam, Winner FROM "
                                     f"tournament WHERE MessageID = {draft_id} AND "
                                     f"RoundNumber = {round_number} AND "
                                     f"MatchNumber = {match_number}")

            if current_match[4] is None and current_match[3] != "bye":
                return current_match
            
            match_number += 1

        round_number += 1

    return None


def get_current_round(ctx):
    current_match = get_current_match(ctx)
    current_round = current_match[0]

    return current_round


def embed_current_match(ctx):
    current_match = get_current_match(ctx)
    embed = Embed(title=f"Current Match")

    red_captain_user = ctx.guild.get_member(current_match[2])
    red_captain = red_captain_user.display_name
    
    if current_match[3] != "bye":
        blue_captain_user = ctx.guild.get_member(current_match[3])
        blue_captain = blue_captain_user.display_name

    else:
        blue_captain = current_match[3]

    winner = "Awaiting match result"

    match_data = f"Red Team: {red_captain}\n"\
                 f"vs \n Blue Team: {blue_captain}\n\n"\
                 f"Winner: {winner}\n\n"\
                  "Use the >winner [@mention] if you have the Draft "\
                  "Admin role to assign the winner of the current match."

    embed.add_field(name=f"Round {current_match[0]}: Match {current_match[1]}",
                    value=match_data, inline=False)

    return embed


def embed_current_round(ctx):
    draft_id = get_draft_id(ctx)
    current_round = get_current_round(ctx)
    rounds = round_count(ctx)
    embed = Embed(title=f"Round {current_round} Matches")

    match_number = 1
    while match_number <= 2**(rounds - current_round):
        match = db.record("SELECT MatchNumber, RedTeam, "
                          "BlueTeam, Winner FROM tournament "
                         f"WHERE MessageID = {draft_id} AND "
                         f"RoundNumber = {current_round} AND "
                         f"MatchNumber = {match_number}")

        red_captain_user = ctx.guild.get_member(match[1])
        red_captain = red_captain_user.display_name

        if match[2] != "bye":
            blue_captain_user = ctx.guild.get_member(match[2])
            blue_captain = blue_captain_user.display_name

        else:
            blue_captain = match[2]
            
        winner = "" 

        if match[3] is None:
            winner = "Awaiting match result"

        else:
            match_winner = ctx.guild.get_member(match[3])
            winner = match_winner.display_name 

        match_data = f"Red Team: {red_captain}\n"\
                     f"vs \n Blue Team: {blue_captain}\n\n"\
                     f"Winner: {winner}"

        embed.add_field(name=f"Match {match_number}", value=match_data, inline=True)

        match_number += 1

    return embed


def bye_match(ctx):
    match = get_current_match(ctx)
    
    return match[3] != "bye" 


class Tournament(Cog):
    def __init__(self, bot):
        self.bot = bot


    @Cog.listener()
    async def on_ready(self):
        if not self.bot.ready:
            self.bot.cogs_ready.ready_up("tournament")


    @command(name="createdraft")
    async def create_draft(self, ctx):
        """Initiates a draft tournament. Must have the 'Draft Admin' role to use this command."""

        if (user_authorized(ctx)):

            if not draft_exists(ctx):
                embed = Embed(title="Draft Tournament",
                        colour=ctx.author.colour)
                
                information = (f"React with: {checkmark} to join the draft tournament! The tournament admin can "
                                "end registration with the command: \n>register [team size] \n\nEnsure that the total "
                                "number of players registered is divisible by the team size to avoid "
                                "substitutes.\n\n After registration, team captains will be chosen randomly and "
                                "take turns selecting teammates from the remaining pool of players with the "
                                "command: \n>pick [@mention_player]")

                field_title = f"Registration phase. Tournament Admin: {ctx.author.display_name}" 

                embed.add_field(name=field_title, value=information, inline=False)

                message = await ctx.send(embed=embed)
                db.execute("INSERT INTO draftMessage (MessageID, ChannelID) VALUES (?, ?)", message.id,
                            message.channel.id) 

                await message.add_reaction(checkmark)

            else:
                await ctx.send("Error, draft already exists. Use the >wipedraft command before starting a new draft.")

        else:
            await ctx.send("Error, you need the 'Draft Admin' role to initiate a draft tournament.")


    @command(name="wipedraft")
    async def wipe_draft(self, ctx):
        if (user_authorized(ctx)):

            if draft_exists(ctx):
                draft_id = get_draft_id(ctx)
                draft_message = await ctx.channel.fetch_message(draft_id)

                db.execute("DELETE FROM draftMessage WHERE MessageID = ?", draft_id)
                await draft_message.delete()

                await ctx.send("Draft wiped.")

            else:
                await ctx.send("Error, no draft found.")

        else:
            await ctx.send("Error, you need the 'Draft Admin' role to use this command.")


    @command(name="register")
    async def register_draft(self, ctx, team_size: int):
        if (user_authorized(ctx)):

            if not registration_exists(ctx): 

                if get_draft_id(ctx) is not None:
                    draft_id = get_draft_id(ctx)

                    db.execute("UPDATE draftMessage "
                              f"SET TeamSize = {team_size} "
                              f"WHERE MessageID = {draft_id}")

                    draft_message = await ctx.channel.fetch_message(draft_id)
                    player_list = []

                    for reaction in draft_message.reactions:
                        if reaction.emoji == checkmark:
                            async for user in reaction.users():
                                if user != self.bot.user:
                                    player_list.append(user)

                    random.shuffle(player_list)

                    for player in player_list:
                        db.execute("INSERT INTO draftPlayers "
                                   "(MessageID, PlayerID) VALUES (?, ?)", draft_id, player.id)

                    captains = random.sample(player_list, math.floor(len(player_list) / team_size))

                    i = 0
                    for captain in captains:
                        db.execute("UPDATE draftPlayers " 
                                  f"SET Team = {captain.id}, "
                                   "    Captain = True, "
                                  f"    DraftOrder = {i} " 
                                  f"WHERE PlayerID = {captain.id}")
                        i += 1
                    
                    await ctx.send(embed=draft_embed(ctx))

                    if (team_size == 1):
                        generate_bracket(ctx)
                        populate_bracket(ctx)
                        embed = embed_current_round(ctx)
                        await ctx.send(embed=embed)

                        embed = embed_current_match(ctx)
                        await ctx.send(embed=embed)
                        

                else:
                    await ctx.send("No draft tournament found, try using the >createdraft command first.")

            else:
                await ctx.send("Error, registration has already been completed.")

        else:
            await ctx.send("You need the 'Draft Admin' role to complete draft registration.")
            

    @command(name="generatebracket")
    async def generate_bracket(self, ctx):
        if user_authorized(ctx):

            if bracket_exists(ctx):
                await ctx.send("Error, a bracket already exists")

            else:
                generate_bracket(ctx)
                populate_bracket(ctx)
                embed = embed_current_round(ctx)
                await ctx.send(embed=embed)

                embed = embed_current_match(ctx)
                await ctx.send(embed=embed)

        else:
            await ctx.send("Error, you need the 'Draft Admin' role to use this command.")


    @command(name="wiperegistration")
    async def wipe_registration(self, ctx):
        if user_authorized(ctx):

            if registration_exists(ctx):
                draft_id = get_draft_id(ctx)
                db.execute("UPDATE draftMessage "
                          f"SET TeamSize = NULL "
                          f"WHERE MessageID = ?", draft_id)

                db.execute("DELETE FROM draftPlayers WHERE MessageID = ?", draft_id)

                await ctx.send("Registration wiped.")

            else:
                await ctx.send("Error, there is no registration to wipe.")

        else:
            await ctx.send("Error, you need the 'Draft Admin' role to use this command.")


    @command(name="wipebracket")
    async def wipe_bracket(self, ctx):
        if user_authorized(ctx):

            if bracket_exists(ctx):
                draft_id = get_draft_id(ctx)
                db.execute("DELETE FROM tournament WHERE MessageID = ?", draft_id)

                await ctx.send("Bracket wiped.")

            else:
                await ctx.send("Error, there is no bracket to wipe.")

        else:
            await ctx.send("Error, you need the 'Draft Admin' role to use this command.")


    @command(name="pick")
    async def pick_player(self, ctx, draft_pick: Member):
        if team_size(ctx) is not None:

            if draft_pool(ctx):

                if ctx.author is current_captain(ctx):

                    if draft_pick in draft_pool(ctx):

                        db.execute("UPDATE draftPlayers "
                                  f"SET Team = {ctx.author.id} "
                                  f"WHERE PlayerID = {draft_pick.id}")

                        await ctx.send(f"{ctx.author.display_name} has chosen: {draft_pick.display_name}")

                        if draft_pool(ctx):
                            await ctx.send(embed=draft_embed(ctx))

                        else:
                            generate_bracket(ctx)
                            populate_bracket(ctx)
                            embed = embed_current_round(ctx)
                            await ctx.send(embed=embed)

                            embed = embed_current_match(ctx)
                            await ctx.send(embed=embed)

                    else:
                        await ctx.send("Player not found in draft pool.")

                else:
                    await ctx.send(f"Wrong order, it is {current_captain(ctx).display_name}'s turn to pick.'")

            else:
                await ctx.send("Error, draft is already completed.")

        else:
            await ctx.send("Draft registration has not been completed yet, try the >register [teamsize] command.")


    @command(name="winner")
    async def assign_winner(self, ctx, winner: Member):
        if user_authorized(ctx):
            match = get_current_match(ctx)
            current_round = match[0]
            match_number = match[1]
            red_captain = ctx.guild.get_member(match[2])
            blue_captain = ctx.guild.get_member(match[3])

            if winner == red_captain or blue_captain:
                db.execute("UPDATE tournament "
                          f"SET Winner = {winner.id} "
                          f"WHERE RoundNumber = {current_round} "
                          f"AND MatchNumber = {match_number}")

                if current_round != round_count(ctx):
                    next_match = math.ceil(match_number / 2)

                    if match_number % 2 == 0:
                        next_team = "BlueTeam"

                    else:
                        next_team = "RedTeam"

                    db.execute("UPDATE tournament "
                              f"SET {next_team} = {winner.id} "
                              f"WHERE RoundNumber = {current_round + 1} "
                              f"AND MatchNumber = {next_match}")

                    embed = embed_current_match(ctx)

                    await ctx.send(embed=embed)

                else:
                    await ctx.send(f"Congratulations, {winner.display_name} has won the tournament!")
                        

            else:
                await ctx.send("Error, winner must be a captain from the current match.")

        else:
            await ctx.send("Error, you need the 'Draft Admin' role to use this command.")


    @command(name="team")
    async def show_team(self, ctx, player: Member):
        if team_size(ctx) is not None:
            
            if player in players(ctx):

                if player not in draft_pool(ctx):
                    captain = get_captain(ctx, player)
                    player_list = team_list(ctx, captain)

                    embed = Embed(title="Draft Team")
                    embed.add_field(name=f"Captain: {captain.display_name}", value=player_list, inline=False)
                    await ctx.send(embed=embed)

                else:
                    await ctx.send("That member does not have a team yet.")

            else:
                await ctx.send("That member is not registered as a Player.")

        else:
            await ctx.send("Draft registration has not been completed yet, try the >register [teamsize] command.")


    @command(name="teams")
    async def show_teams(self, ctx):
        if team_size(ctx) is not None:
            captains_list = captains(ctx)

            embed = Embed(title="Draft Teams")

            for captain in captains_list:
                player_list = team_list(ctx, captain)
                embed.add_field(name=f"Captain: {captain.display_name}", value=player_list, inline=True)

            await ctx.send(embed=embed)

        else:
            await ctx.send("Draft registration has not been completed yet, try the >register [teamsize] command.")

    @command(name="currentmatch")
    async def current_match(self, ctx):
        get_current_match(ctx)


    @Cog.listener()
    async def on_raw_reaction_add(self, payload):
        print(f"[RAW] {payload.member.display_name} reacted with {payload.emoji.name}")

    @Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        member = self.bot.guild.get_member(payload.user_id)
        print(f"[RAW] {member.display_name} removed reaction of {payload.emoji.name}")


def setup(bot):
    bot.add_cog(Tournament(bot))
